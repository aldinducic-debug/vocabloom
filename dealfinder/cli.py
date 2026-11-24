"""Command line: `python -m dealfinder {login,run,watch,report}`."""

from __future__ import annotations

import argparse
import sys
import time

from .config import load_config
from .db import Store
from .report import push_ntfy, write_report
from .scoring import in_price_range, is_excluded, judge


def run_once(cfg, headless: bool) -> int:
    from .scraper import LoginRequired, open_browser, scrape

    s = cfg.settings
    store = Store(s.db_path)
    pw, ctx = open_browser(s, headless=headless)
    found = 0
    try:
        for search in cfg.searches:
            batch = []
            for area in cfg.areas_for(search):
                print(f"→ {search.query!r} in {area.name} ({area.location})", flush=True)
                try:
                    listings = scrape(ctx, area, search, s)
                except LoginRequired as e:
                    print(f"  {e}", file=sys.stderr)
                    return 2
                except Exception as e:  # one bad page shouldn't kill the whole run
                    print(f"  skipped: {e}", file=sys.stderr)
                    continue
                for item in listings:
                    store.upsert(item)
                batch.extend(listings)
                print(f"  {len(listings)} listings", flush=True)

            # Typical price = this run's results plus the last 30 days of history, across all areas.
            comparables = store.recent_prices(search.query)
            for item in batch:
                if is_excluded(item, search, s.global_exclude) or not in_price_range(item, search):
                    continue
                v = judge(item, search, comparables,
                          threshold=s.deal_threshold, min_comparables=s.min_comparables)
                store.mark(item.id, item.query, is_deal=v.is_deal, score=v.score,
                           typical=v.typical_price, reasons=v.reasons)
                found += v.is_deal
    finally:
        ctx.close()
        pw.stop()

    path = write_report(store.deals(), s.report_path)
    fresh = store.unnotified_deals()
    if fresh and s.ntfy_topic:
        try:
            push_ntfy(s.ntfy_topic, fresh)
        except Exception as e:
            print(f"notification failed: {e}", file=sys.stderr)
    store.mark_notified([(r["id"], r["query"]) for r in fresh])
    print(f"\n{found} deals this run, {len(fresh)} new. Report: {path.resolve()}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="dealfinder", description="Find good deals on Facebook Marketplace.")
    ap.add_argument("-c", "--config", default="config.toml")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="open a browser window so you can log in to Facebook once")
    r = sub.add_parser("run", help="search every area once and write the report")
    r.add_argument("--headless", action="store_true")
    w = sub.add_parser("watch", help="run on a loop (interval_minutes in config)")
    w.add_argument("--headless", action="store_true")
    sub.add_parser("report", help="rebuild the HTML report from saved data")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.cmd == "login":
        from .scraper import login
        login(cfg.settings)
        return 0
    if args.cmd == "report":
        print(write_report(Store(cfg.settings.db_path).deals(), cfg.settings.report_path).resolve())
        return 0
    if args.cmd == "run":
        return run_once(cfg, args.headless)
    while True:
        code = run_once(cfg, args.headless)
        if code == 2:
            return code
        print(f"Sleeping {cfg.settings.interval_minutes} min…")
        time.sleep(cfg.settings.interval_minutes * 60)
