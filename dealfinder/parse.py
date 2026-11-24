"""Turn raw Marketplace listing-card text into structured listings.

Facebook's DOM class names are obfuscated and change constantly, so we don't
rely on them. Instead the scraper grabs every link to /marketplace/item/<id>
and hands us the card's visible text, which reliably looks like:

    $120$180          <- current price, optionally followed by the old price
    IKEA Kallax shelf <- title
    Austin, TX        <- location
    12K km            <- (vehicles only) mileage

This module is pure Python so it can be unit-tested without a browser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ITEM_ID_RE = re.compile(r"/marketplace/item/(\d+)")
PRICE_TOKEN_RE = re.compile(r"(?:[$€£]|CA\$|A\$)\s?([\d,]+(?:\.\d{1,2})?)|\b(free)\b", re.I)


@dataclass
class Listing:
    id: str
    url: str
    title: str
    price: float | None
    original_price: float | None
    location_text: str
    image_url: str | None = None
    # Filled in by the scraper / scorer:
    query: str = ""
    area: str = ""
    area_note: str = ""
    extra: dict = field(default_factory=dict)


def parse_item_id(href: str) -> str | None:
    m = ITEM_ID_RE.search(href or "")
    return m.group(1) if m else None


def parse_prices(line: str) -> list[float]:
    """'$1,200$1,500' -> [1200.0, 1500.0]; 'Free' -> [0.0]."""
    out: list[float] = []
    for num, free in PRICE_TOKEN_RE.findall(line or ""):
        if free:
            out.append(0.0)
        elif num:
            out.append(float(num.replace(",", "")))
    return out


def _looks_like_price_line(line: str) -> bool:
    stripped = PRICE_TOKEN_RE.sub("", line).strip()
    return bool(parse_prices(line)) and len(stripped) <= 2


def parse_card(href: str, text: str, image_url: str | None = None) -> Listing | None:
    item_id = parse_item_id(href)
    if not item_id:
        return None

    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    if not lines:
        return None

    price = original = None
    rest = lines
    if _looks_like_price_line(lines[0]):
        prices = parse_prices(lines[0])
        price = prices[0]
        original = prices[1] if len(prices) > 1 else None
        rest = lines[1:]
        # Sometimes the old price is rendered on its own line.
        if rest and original is None and _looks_like_price_line(rest[0]):
            original = parse_prices(rest[0])[0]
            rest = rest[1:]

    title = rest[0] if rest else ""
    location = rest[1] if len(rest) > 1 else ""

    return Listing(
        id=item_id,
        url=f"https://www.facebook.com/marketplace/item/{item_id}/",
        title=title,
        price=price,
        original_price=original,
        location_text=location,
        image_url=image_url,
    )
