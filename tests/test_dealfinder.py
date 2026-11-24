import time
from pathlib import Path

import pytest

from dealfinder.config import Search, Settings, Area, load_config
from dealfinder.db import Store
from dealfinder.parse import parse_card, parse_prices
from dealfinder.report import write_report
from dealfinder.scoring import in_price_range, is_excluded, judge, typical_price
from dealfinder.scraper import search_url

ROOT = Path(__file__).resolve().parents[1]


def test_parse_prices():
    assert parse_prices("$1,200$1,500") == [1200.0, 1500.0]
    assert parse_prices("Free") == [0.0]
    assert parse_prices("CA$45") == [45.0]
    assert parse_prices("IKEA desk") == []


def test_parse_card_with_price_drop():
    item = parse_card("/marketplace/item/123456/?ref=search", "$80$150\nStanding desk, electric\nAustin, TX")
    assert item.id == "123456"
    assert item.price == 80 and item.original_price == 150
    assert item.title == "Standing desk, electric"
    assert item.location_text == "Austin, TX"
    assert item.url == "https://www.facebook.com/marketplace/item/123456/"


def test_parse_card_price_drop_on_two_lines_and_title_with_dollar():
    item = parse_card("/marketplace/item/9/", "$300\n$400\nPS5 disc - paid $500\nDallas, TX")
    assert (item.price, item.original_price) == (300, 400)
    assert item.title == "PS5 disc - paid $500"


def test_parse_card_rejects_non_items():
    assert parse_card("/marketplace/category/vehicles", "Vehicles") is None


def test_typical_price_needs_enough_data_and_ignores_placeholders():
    assert typical_price([100, 120], 5) is None
    assert typical_price([1, 0, 100, 110, 120, 130, 140], 5) == 120


def test_judge_flags_cheap_listing():
    item = parse_card("/marketplace/item/1/", "$60\nStanding desk - moving must go\nAustin")
    v = judge(item, Search("standing desk"), [200, 210, 190, 220, 180], threshold=0.3, min_comparables=5)
    assert v.is_deal
    assert v.score >= 0.7
    assert any("motivated" in r for r in v.reasons)


def test_judge_ignores_normal_price():
    item = parse_card("/marketplace/item/1/", "$195\nStanding desk\nAustin")
    v = judge(item, Search("standing desk"), [200, 210, 190, 220, 180], threshold=0.3, min_comparables=5)
    assert not v.is_deal


def test_judge_target_price_without_history():
    item = parse_card("/marketplace/item/1/", "$70\nStanding desk\nAustin")
    v = judge(item, Search("standing desk", target_price=80), [], threshold=0.3, min_comparables=5)
    assert v.is_deal


def test_judge_rejects_dollar_one_bait():
    item = parse_card("/marketplace/item/1/", "$1\nPS5\nAustin")
    v = judge(item, Search("ps5"), [400] * 6, threshold=0.3, min_comparables=5)
    assert not v.is_deal


def test_filters():
    item = parse_card("/marketplace/item/1/", "$50\nPS5 controller only\nAustin")
    s = Search("ps5", min_price=150, exclude=["controller only"])
    assert is_excluded(item, s, [])
    assert not in_price_range(item, s)
    wanted = parse_card("/marketplace/item/2/", "$50\nWANTED: ps5\nAustin")
    assert is_excluded(wanted, Search("ps5"), Settings().global_exclude)


def test_search_url():
    url = search_url(Area("Home", "austin", 40), Search("standing desk", max_price=250), Settings())
    assert url.startswith("https://www.facebook.com/marketplace/austin/search?")
    assert "query=standing+desk" in url and "maxPrice=250" in url and "radius=40" in url


def test_example_config_loads():
    cfg = load_config(ROOT / "config.example.toml")
    assert [a.name for a in cfg.areas_for(cfg.searches[2])] == ["Home", "Sis"]


def test_bad_area_reference(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('[[areas]]\nname="Home"\nlocation="x"\n[[searches]]\nquery="q"\nareas=["Nope"]\n')
    with pytest.raises(ValueError, match="unknown areas"):
        load_config(p)


def test_store_and_report_roundtrip(tmp_path):
    store = Store(tmp_path / "d.sqlite3")
    item = parse_card("/marketplace/item/42/", "$60$120\nKayak <3\nHouston")
    item.query, item.area, item.area_note = "kayak", "Sis", "Sis drives up"
    assert store.upsert(item) is True
    assert store.upsert(item) is False
    assert store.recent_prices("kayak") == [60]
    store.mark("42", "kayak", is_deal=True, score=0.5, typical=120, reasons=["50% under"])
    assert len(store.unnotified_deals()) == 1
    store.mark_notified([("42", "kayak")])
    assert store.unnotified_deals() == []
    html = write_report(store.deals(), tmp_path / "r.html").read_text()
    assert "Kayak &lt;3" in html and "Sis drives up" in html and "$60" in html
