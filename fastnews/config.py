"""Configuration loading and shared constants."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEEDS_FILE = os.path.join(ROOT, "feeds.json")
SITE_DIR = os.path.join(ROOT, "site")
FIXTURES_DIR = os.path.join(ROOT, "data", "fixtures")

# A browser-ish User-Agent; some feeds reject the default urllib agent.
USER_AGENT = "Mozilla/5.0 (compatible; FastNews/1.0; +https://github.com/sirbot32/fast-news)"


@dataclass(frozen=True)
class Feed:
    name: str
    url: str
    category: str = "Top"


def load_feeds(path: str = FEEDS_FILE) -> list[Feed]:
    """Read feeds.json into a list of Feed objects."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    feeds = []
    for entry in data.get("feeds", []):
        feeds.append(
            Feed(
                name=entry["name"].strip(),
                url=entry["url"].strip(),
                category=entry.get("category", "Top").strip() or "Top",
            )
        )
    if not feeds:
        raise ValueError(f"No feeds defined in {path}")
    return feeds
