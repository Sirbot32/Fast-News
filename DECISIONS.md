# Decisions Log

Persistent memory across sessions. Newest first.

---

## 2026-06-23 — Barebones Digg-style redesign

User feedback: the first design read "too AI" and cluttered. Added two advisors
to the council: **the Designer** and **the Consumer Analyst**. Both converged on:
strip to a numbered list on a white background, one accent for links only,
hairline dividers instead of cards, a single dark-mode toggle button, no emoji,
no pills. Consumer Analyst's rule: the visitor has ~30 seconds — anything that
isn't a headline, a one-line summary, or a link is friction.

Implemented in `build.py`:
- White default theme; dark mode via a single text toggle that persists in
  `localStorage` (does not auto-follow OS, so "white background" is the default).
- Each story is a row: left **count box** (distinct-source count) + headline +
  summary (top 5 only) + sources·time meta + "Read full story →".
- Category filter is plain text links, not buttons.
- Removed: dark default, gradient/card styling, 🔥 emoji, the explainer tagline,
  domain line, `_domain()` helper.
- Confirmed: no accounts, no subscriptions, opens as a single static file.


## 2026-06-23 — v1 scope agreed (via the Council)

**Brief:** A fast way to get the most important news of the week, plus a historic
archive (most important news from the 2000s on). Digg-like. For people short on
time. One person executing. Must have important news available at a click,
anywhere, anytime.

**Council outcome:** The advisors converged on *not* building an HTML scraper.
Scraping live news sites is fragile (breaks on redesigns), often against ToS,
and paywalled — bad fit for a one-person project. "Scraper" was a chosen
mechanism, not the goal. The goal is *aggregated important news*.

**Chairman's call — agreed v1 scope:**
- **Source:** RSS/Atom feeds outlets publish themselves (legal, stable, free),
  configured in `feeds.json`. No HTML scraping.
- **Importance signal:** cross-source coverage — a story carried by many
  outlets ranks higher. Small recency boost breaks ties at equal coverage.
- **Output:** a single static, mobile-friendly page (Digg-style list) +
  `data.json`. No backend, no accounts, no voting.
- **Window:** rolling 7 days ("this week").
- **Hosting (per user):** run locally for v1. Cloud hosting deferred to v2
  (alongside other apps the user wants to deploy).
- **Tech:** Python standard library only — zero dependencies, no `pip install`.
  Chosen for the one-person maintenance constraint and because the sandbox
  couldn't install `feedparser` reliably anyway.

**Explicitly NOT in v1:** HTML scraping of protected/paywalled sites; user
accounts / voting / comments; a live server; the historic archive.

**v2 (the differentiator):** "Most important news of [year]" pages, 2000→present,
seeded from structured year-in-review data (e.g. Wikipedia current-events), not
scraped from archives. Cloud-hosted. Optional weekly email digest.

**Implementation notes:**
- Stdlib RSS *and* Atom parser in `fetch.py` (namespace-agnostic via
  ElementTree); per-feed failures never abort a run.
- Clustering uses token overlap-coefficient + `difflib` ratio (Jaccard alone
  over-penalized headlines that share key entities but add extra words).
- Offline sample fallback (`data/fixtures/` + `sample_data.py`) so the pipeline
  and site always produce output even with no network. The dev sandbox's
  network is allowlisted to PyPI only, so live feeds returned HTTP 403 here —
  expected to work on the user's machine.
- The data format (`site/data.json`) is shaped so historic entries can slot in
  later without changing the schema.
