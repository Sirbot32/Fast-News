# Fast·News

The week that mattered — important news at a click, ranked by **how many outlets carried each story**.

Fast-News pulls headlines from a set of RSS/Atom feeds, groups near-duplicate
headlines into one story, and ranks stories by **cross-source coverage**: a
story carried by many independent outlets is treated as more important than one
carried by a single outlet (with a small recency boost to keep things fresh).
The output is a single static, mobile-friendly page you can open anywhere.

Think *Digg's front page*, derived automatically — no accounts, no voting, no server.

## Why this design

Scraping individual news sites is fragile and often against their terms. Instead
Fast-News reads the **RSS/Atom feeds outlets publish themselves** — stable,
legal, and free — and infers importance from agreement across sources. See
[`DECISIONS.md`](DECISIONS.md) for the full reasoning.

## Requirements

Python 3.10+. **No dependencies, no `pip install`** — standard library only.

## Usage

```bash
# Fetch live feeds and build the site into ./site
python3 main.py

# Build, then serve it locally and open the browser
python3 main.py --serve

# Force offline sample data (no network needed) — great for a quick look
python3 main.py --sample

# Tweak the window / size / clustering
python3 main.py --days 3 --max 40 --threshold 0.5
```

Open `site/index.html` in any browser, or use `--serve` to view at
`http://localhost:8000`.

If no live feed is reachable (e.g. no network), Fast-News automatically falls
back to bundled sample data so you always get a working page.

## Configuring sources

Edit [`feeds.json`](feeds.json). Each entry:

```json
{ "name": "BBC", "url": "https://feeds.bbci.co.uk/news/rss.xml", "category": "Top" }
```

- `name` — shown as the source badge.
- `url` — any RSS or Atom feed.
- `category` — used for the on-page filter buttons (e.g. `Top`, `World`).

Add or remove feeds freely; more sources = better coverage signal.

## How ranking works

1. **Fetch** every feed (last 7 days by default), de-duplicating identical links.
2. **Cluster** headlines that describe the same event, using token overlap +
   string similarity (`fastnews/rank.py`).
3. **Score** each cluster ≈ `distinct_source_count + small_recency_boost`.
   Coverage dominates; recency only separates stories of equal reach.
4. **Build** a static `site/index.html` + `site/data.json`.

## Project layout

```
feeds.json            # your news sources
main.py               # CLI entry point (fetch → rank → build)
fastnews/
  config.py           # load feeds, constants
  fetch.py            # stdlib RSS/Atom fetch + parse
  rank.py             # clustering + coverage scoring
  build.py            # static HTML/JSON renderer
  sample_data.py      # offline fallback (parses data/fixtures/)
data/fixtures/        # sample feeds for offline mode
tests/                # python3 -m unittest discover -s tests
site/                 # generated output (gitignored)
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Roadmap

- **v1 (this):** live RSS aggregation, coverage ranking, static site, run locally.
- **v2:** cloud-hosted alongside other apps; historic "most important news of
  [year]" pages (2000→present) seeded from structured year-in-review data;
  optional weekly email digest.
