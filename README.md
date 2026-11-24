# Marketplace Deal Finder

Scrolls Facebook Marketplace for you — at home **and** in the cities where your family lives — and flags listings priced well under what that item usually goes for.

- **Multiple areas.** Search your town plus Mom's, your sister's, wherever. Each deal says which area it's in and your note ("Mom can pick it up at Thanksgiving").
- **Real "is this a deal?" math.** Every listing is saved. The typical price for a search is the median of the last 30 days of asking prices across all your areas. Anything 30%+ under it gets flagged (you can change the threshold).
- **Extra signals.** Price drops, "must go / moving / OBO" wording, and your own target price.
- **Junk filtered out.** "$1" bait listings, "WANTED", "for parts", plus your own exclude words.
- **A report and phone alerts.** A clean `deals.html` page you can filter by area, and optional free push notifications via [ntfy](https://ntfy.sh).

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp config.example.toml config.toml   # then edit: your areas + what you're hunting for
python -m dealfinder login           # a browser opens — log in to Facebook once, press Enter
```

To find an area's `location` value, open Marketplace, set the location to that city, and copy what appears after `/marketplace/` in the URL (`austin`, or a long number).

## Use

```bash
python -m dealfinder run        # one pass over every search × area, then writes deals.html
python -m dealfinder watch      # keeps going every interval_minutes
python -m dealfinder report     # rebuild deals.html from saved data
```

Add `--headless` to hide the browser window once it's working.

**Phone alerts:** install the ntfy app, subscribe to a hard-to-guess topic name, and put the same name in `ntfy_topic`.

## Good to know

- Facebook has no public Marketplace API and its terms don't allow automated collection. This tool runs on your own computer with your own login and goes slowly on purpose (random 4–9 s pauses), but heavy use can still get your account rate-limited or flagged. Keep searches and areas reasonable and the interval at an hour or more.
- Facebook changes its page layout often. The scraper only relies on listing links and their visible text, which tends to survive redesigns. If results drop to zero, the parsing in `dealfinder/parse.py` is the place to look.
- The first few runs have little price history, so early on only your `target_price` triggers deals. It gets sharper as data builds up.

## Tests

```bash
pip install pytest && python -m pytest
```
