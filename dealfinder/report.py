"""Write a self-contained HTML page of current deals, and optional phone pushes."""

from __future__ import annotations

import html
import json
import time
import urllib.request
from pathlib import Path


def _card(r) -> str:
    e = html.escape
    img = f'<img src="{e(r["image_url"])}" alt="" loading="lazy">' if r["image_url"] else '<div class="noimg"></div>'
    was = f'<s>${r["original_price"]:,.0f}</s>' if r["original_price"] else ""
    typical = f'<span class="typ">typical ${r["typical_price"]:,.0f}</span>' if r["typical_price"] else ""
    note = f'<div class="note">{e(r["area_note"])}</div>' if r["area_note"] else ""
    return f"""
    <a class="card" href="{e(r["url"])}" target="_blank" rel="noopener"
       data-area="{e(r["area"])}" data-query="{e(r["query"])}">
      {img}
      <div class="body">
        <div class="price">${r["price"]:,.0f} {was} {typical}</div>
        <div class="title">{e(r["title"] or "")}</div>
        <div class="meta"><b>{e(r["area"])}</b> · {e(r["location_text"] or "")} · “{e(r["query"])}”</div>
        {note}
        <div class="why">{e(r["reasons"] or "")}</div>
      </div>
      <div class="score">{r["score"]:.0%}</div>
    </a>"""


def write_report(rows, path: str | Path) -> Path:
    areas = sorted({r["area"] for r in rows})
    chips = "".join(f'<button data-f="{html.escape(a)}">{html.escape(a)}</button>' for a in areas)
    cards = "".join(_card(r) for r in rows) or '<p class="empty">No deals yet — the next run will look again.</p>'
    stamp = time.strftime("%b %d, %I:%M %p")
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Marketplace Deals</title>
<style>
:root {{ --bg:#f6f7f9; --card:#fff; --ink:#15181d; --mute:#5d6673; --line:#e3e6ea; --accent:#0a7c4a; --chip:#e9eef3; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#111418; --card:#1a1f25; --ink:#e9edf1; --mute:#9aa4b1; --line:#2a313a; --accent:#3ccf8e; --chip:#232a33; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.4 system-ui,-apple-system,sans-serif; }}
header {{ padding:20px 16px 8px; max-width:900px; margin:auto; }}
h1 {{ margin:0; font-size:22px; }} .sub {{ color:var(--mute); font-size:13px; }}
nav {{ display:flex; gap:8px; flex-wrap:wrap; padding:8px 16px; max-width:900px; margin:auto; }}
nav button {{ border:0; background:var(--chip); color:var(--ink); padding:6px 12px; border-radius:999px; cursor:pointer; font:inherit; }}
nav button.on {{ background:var(--accent); color:#fff; }}
main {{ max-width:900px; margin:auto; padding:8px 16px 40px; display:grid; gap:10px; }}
.card {{ display:grid; grid-template-columns:96px 1fr auto; gap:12px; background:var(--card); border:1px solid var(--line);
         border-radius:12px; padding:10px; color:inherit; text-decoration:none; align-items:start; }}
.card img, .noimg {{ width:96px; height:96px; object-fit:cover; border-radius:8px; background:var(--chip); }}
.price {{ font-weight:700; font-size:17px; }} .price s {{ color:var(--mute); font-weight:400; font-size:13px; }}
.typ {{ color:var(--mute); font-weight:400; font-size:12px; margin-left:4px; }}
.title {{ margin:2px 0; }} .meta, .why {{ color:var(--mute); font-size:13px; }}
.note {{ font-size:13px; margin-top:2px; }} .why {{ color:var(--accent); }}
.score {{ font-weight:700; color:var(--accent); }} .empty {{ color:var(--mute); }}
@media (max-width:480px) {{ .card {{ grid-template-columns:72px 1fr; }} .card img, .noimg {{ width:72px; height:72px; }} .score {{ display:none; }} }}
</style></head><body>
<header><h1>Marketplace Deals</h1><div class="sub">{len(rows)} deals · updated {stamp}</div></header>
<nav><button class="on" data-f="">All areas</button>{chips}</nav>
<main>{cards}</main>
<script>
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {{
  document.querySelectorAll('nav button').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.card').forEach(c => c.style.display = !b.dataset.f || c.dataset.area === b.dataset.f ? '' : 'none');
}});
</script></body></html>"""
    out = Path(path)
    out.write_text(page)
    return out


def push_ntfy(topic: str, rows) -> None:
    """Free phone notifications via https://ntfy.sh — install the app and subscribe to your topic."""
    for r in rows[:10]:
        body = f'${r["price"]:,.0f} · {r["area"]} · {r["reasons"]}'
        req = urllib.request.Request(
            f"https://ntfy.sh/{topic}",
            data=body.encode(),
            headers={"Title": (r["title"] or "Deal")[:80].encode("ascii", "ignore").decode(), "Click": r["url"], "Tags": "moneybag"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
