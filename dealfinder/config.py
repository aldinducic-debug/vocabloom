"""Load the TOML config (see config.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Area:
    name: str                 # "Home", "Mom & Dad", ...
    location: str             # Marketplace location slug or numeric id, e.g. "austin" or "108424279189115"
    radius_km: int = 40
    note: str = ""            # shown on each deal, e.g. "Mom can grab it Sunday"


@dataclass
class Search:
    query: str
    max_price: float | None = None
    min_price: float | None = None
    target_price: float | None = None   # anything at/under this is always a deal
    exclude: list[str] = field(default_factory=list)
    areas: list[str] = field(default_factory=list)  # empty = all areas


@dataclass
class Settings:
    deal_threshold: float = 0.30        # 30% under the typical price
    min_comparables: int = 5
    days_since_listed: int = 7
    scroll_rounds: int = 6
    delay_seconds: tuple[float, float] = (4.0, 9.0)
    interval_minutes: int = 60
    ntfy_topic: str = ""
    profile_dir: str = ".browser-profile"
    db_path: str = "deals.sqlite3"
    report_path: str = "deals.html"
    global_exclude: list[str] = field(default_factory=lambda: [
        "broken", "for parts", "parts only", "wanted", "iso ", "looking for", "rent", "trade only",
    ])


@dataclass
class Config:
    settings: Settings
    areas: list[Area]
    searches: list[Search]

    def areas_for(self, search: Search) -> list[Area]:
        if not search.areas:
            return self.areas
        wanted = {a.lower() for a in search.areas}
        return [a for a in self.areas if a.name.lower() in wanted]


def load_config(path: str | Path) -> Config:
    data = tomllib.loads(Path(path).read_text())
    s = data.get("settings", {})
    if "delay_seconds" in s:
        s["delay_seconds"] = tuple(s["delay_seconds"])
    settings = Settings(**s)
    areas = [Area(**a) for a in data.get("areas", [])]
    searches = [Search(**q) for q in data.get("searches", [])]
    if not areas:
        raise ValueError("config needs at least one [[areas]] entry")
    if not searches:
        raise ValueError("config needs at least one [[searches]] entry")
    names = {a.name.lower() for a in areas}
    for q in searches:
        unknown = [a for a in q.areas if a.lower() not in names]
        if unknown:
            raise ValueError(f"search {q.query!r} references unknown areas: {unknown}")
    return Config(settings, areas, searches)
