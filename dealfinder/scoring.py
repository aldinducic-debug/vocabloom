"""Decide which listings are actually good deals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median

from .config import Search
from .parse import Listing

MOTIVATED_SELLER = re.compile(
    r"\b(must go|moving|need gone|obo|price drop|reduced|quick sale|leaving town|asap)\b", re.I
)


@dataclass
class Verdict:
    listing: Listing
    is_deal: bool
    score: float           # 0..1, higher = better deal
    typical_price: float | None
    reasons: list[str]


def is_excluded(listing: Listing, search: Search, global_exclude: list[str]) -> bool:
    haystack = f" {listing.title.lower()} "
    return any(word.lower() in haystack for word in [*global_exclude, *search.exclude])


def in_price_range(listing: Listing, search: Search) -> bool:
    if listing.price is None:
        return False
    if search.max_price is not None and listing.price > search.max_price:
        return False
    if search.min_price is not None and listing.price < search.min_price:
        return False
    return True


def typical_price(prices: list[float], min_comparables: int) -> float | None:
    """Median of comparable asking prices, ignoring $0 and $1 placeholder listings."""
    real = [p for p in prices if p and p > 1]
    if len(real) < min_comparables:
        return None
    return median(real)


def judge(
    listing: Listing,
    search: Search,
    comparable_prices: list[float],
    *,
    threshold: float,
    min_comparables: int,
) -> Verdict:
    reasons: list[str] = []
    typical = typical_price(comparable_prices, min_comparables)
    price = listing.price if listing.price is not None else 0.0

    score = 0.0
    qualifies = False
    if typical:
        score = max(0.0, 1 - price / typical)
        if score >= threshold:
            qualifies = True
            reasons.append(f"{score:.0%} under the typical ${typical:,.0f}")

    if search.target_price is not None and price <= search.target_price:
        qualifies = True
        reasons.append(f"at/under your target ${search.target_price:,.0f}")
        score = max(score, threshold)

    if listing.original_price and listing.original_price > price:
        drop = 1 - price / listing.original_price
        reasons.append(f"price dropped {drop:.0%} (was ${listing.original_price:,.0f})")
        score += 0.05

    if MOTIVATED_SELLER.search(listing.title):
        reasons.append("motivated seller wording")
        score += 0.05

    # $0/$1 "prices" are usually bait; only trust them if the user wants freebies.
    if price <= 1 and not (search.target_price is not None and search.target_price <= 1):
        return Verdict(listing, False, 0.0, typical, ["placeholder price"])

    return Verdict(listing, qualifies, round(min(score, 1.0), 3), typical, reasons)
