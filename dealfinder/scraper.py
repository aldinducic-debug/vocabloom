"""Drive a real Chromium window through Marketplace search results.

Uses a persistent browser profile so you log in to Facebook once by hand
(`python -m dealfinder login`) and later runs reuse that session. Pacing is
deliberately slow and human-like: this is a personal helper, not a crawler.
"""

from __future__ import annotations

import random
import time
from urllib.parse import quote_plus, urlencode

from .config import Area, Search, Settings
from .parse import Listing, parse_card

MARKETPLACE = "https://www.facebook.com/marketplace"

# Runs in the page: collect every listing card's link, visible text and image.
COLLECT_JS = """
() => {
  const seen = new Set();
  const out = [];
  for (const a of document.querySelectorAll('a[href*="/marketplace/item/"]')) {
    const href = a.getAttribute('href');
    const id = (href.match(/\\/marketplace\\/item\\/(\\d+)/) || [])[1];
    if (!id || seen.has(id)) continue;
    seen.add(id);
    const img = a.querySelector('img');
    out.push({ href, text: a.innerText || '', image: img ? img.src : null });
  }
  return out;
}
"""


def search_url(area: Area, search: Search, settings: Settings) -> str:
    params = {
        "query": search.query,
        "exact": "false",
        "sortBy": "creation_time_descend",
        "daysSinceListed": settings.days_since_listed,
        "radius": area.radius_km,
    }
    if search.max_price is not None:
        params["maxPrice"] = int(search.max_price)
    if search.min_price is not None:
        params["minPrice"] = int(search.min_price)
    return f"{MARKETPLACE}/{quote_plus(area.location)}/search?{urlencode(params)}"


def _pause(settings: Settings) -> None:
    time.sleep(random.uniform(*settings.delay_seconds))


def open_browser(settings: Settings, headless: bool = False):
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        settings.profile_dir,
        headless=headless,
        viewport={"width": 1280, "height": 900},
        locale="en-US",
    )
    return pw, ctx


def login(settings: Settings) -> None:
    pw, ctx = open_browser(settings, headless=False)
    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.facebook.com/login")
        print("Log in to Facebook in the browser window, then come back here and press Enter.")
        input()
    finally:
        ctx.close()
        pw.stop()


class LoginRequired(RuntimeError):
    pass


def scrape(ctx, area: Area, search: Search, settings: Settings) -> list[Listing]:
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(search_url(area, search, settings), wait_until="domcontentloaded")
    _pause(settings)

    if "/login" in page.url or page.locator('input[name="email"]').count():
        raise LoginRequired("Facebook session expired — run `python -m dealfinder login` again.")

    cards: dict[str, dict] = {}
    for _ in range(settings.scroll_rounds):
        for c in page.evaluate(COLLECT_JS):
            cards.setdefault(c["href"], c)
        page.mouse.wheel(0, random.randint(1800, 2800))
        _pause(settings)

    listings = []
    for c in cards.values():
        item = parse_card(c["href"], c["text"], c["image"])
        if item:
            item.query, item.area, item.area_note = search.query, area.name, area.note
            listings.append(item)
    return listings
