"""Offline sample data, parsed from the fixture feeds in data/fixtures/.

Used automatically when live feeds are unreachable (e.g. no network), so the
pipeline and the site always produce something you can look at.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime, timezone

from .config import FIXTURES_DIR, Feed
from .fetch import Article, parse_feed

# Map fixture filename -> (display name, category).
_META = {
    "bbc": ("BBC", "Top"),
    "cnn": ("CNN", "Top"),
    "guardian": ("Guardian", "World"),
    "npr": ("NPR", "World"),
}


def load_sample() -> tuple[list[Article], datetime]:
    """Return (articles, reference_now).

    reference_now is anchored to the newest fixture timestamp so recency
    scoring behaves sensibly no matter what date you run this on.
    """
    articles: list[Article] = []
    for path in sorted(glob.glob(os.path.join(FIXTURES_DIR, "*.xml"))):
        key = os.path.splitext(os.path.basename(path))[0]
        name, category = _META.get(key, (key.upper(), "Top"))
        with open(path, "rb") as fh:
            raw = fh.read()
        articles.extend(parse_feed(raw, Feed(name=name, url=path, category=category)))
    now = max((a.published for a in articles), default=datetime.now(timezone.utc))
    return articles, now
