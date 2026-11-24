"""SQLite storage: remembers every listing seen so price history improves over time."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .parse import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id TEXT NOT NULL,
    query TEXT NOT NULL,
    area TEXT NOT NULL,
    area_note TEXT DEFAULT '',
    title TEXT,
    price REAL,
    original_price REAL,
    location_text TEXT,
    url TEXT,
    image_url TEXT,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL,
    is_deal INTEGER DEFAULT 0,
    score REAL DEFAULT 0,
    typical_price REAL,
    reasons TEXT DEFAULT '',
    notified INTEGER DEFAULT 0,
    PRIMARY KEY (id, query)
);
CREATE INDEX IF NOT EXISTS idx_query_seen ON listings(query, last_seen);
"""


class Store:
    def __init__(self, path: str | Path):
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def upsert(self, listing: Listing) -> bool:
        """Insert or refresh a listing. Returns True if it was new for this query."""
        now = time.time()
        cur = self.conn.execute(
            "SELECT 1 FROM listings WHERE id=? AND query=?", (listing.id, listing.query)
        )
        is_new = cur.fetchone() is None
        self.conn.execute(
            """
            INSERT INTO listings (id, query, area, area_note, title, price, original_price, location_text,
                                  url, image_url, first_seen, last_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id, query) DO UPDATE SET
                title=excluded.title, price=excluded.price,
                original_price=excluded.original_price, location_text=excluded.location_text,
                image_url=COALESCE(excluded.image_url, image_url), last_seen=excluded.last_seen
            """,
            (listing.id, listing.query, listing.area, listing.area_note, listing.title, listing.price,
             listing.original_price, listing.location_text, listing.url, listing.image_url, now, now),
        )
        self.conn.commit()
        return is_new

    def recent_prices(self, query: str, days: int = 30) -> list[float]:
        cutoff = time.time() - days * 86400
        rows = self.conn.execute(
            "SELECT price FROM listings WHERE query=? AND last_seen>=? AND price IS NOT NULL",
            (query, cutoff),
        )
        return [r["price"] for r in rows]

    def mark(self, listing_id: str, query: str, *, is_deal: bool, score: float,
             typical: float | None, reasons: list[str]) -> None:
        self.conn.execute(
            "UPDATE listings SET is_deal=?, score=?, typical_price=?, reasons=? WHERE id=? AND query=?",
            (int(is_deal), score, typical, " · ".join(reasons), listing_id, query),
        )
        self.conn.commit()

    def unnotified_deals(self) -> list[sqlite3.Row]:
        return list(self.conn.execute(
            "SELECT * FROM listings WHERE is_deal=1 AND notified=0 ORDER BY score DESC"
        ))

    def mark_notified(self, ids: list[tuple[str, str]]) -> None:
        self.conn.executemany("UPDATE listings SET notified=1 WHERE id=? AND query=?", ids)
        self.conn.commit()

    def deals(self, days: int = 7) -> list[sqlite3.Row]:
        cutoff = time.time() - days * 86400
        return list(self.conn.execute(
            "SELECT * FROM listings WHERE is_deal=1 AND last_seen>=? ORDER BY score DESC, last_seen DESC",
            (cutoff,),
        ))
