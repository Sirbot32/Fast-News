"""Fetch and parse RSS/Atom feeds using only the standard library."""

from __future__ import annotations

import urllib.request
import urllib.error
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from .config import Feed, USER_AGENT


@dataclass
class Article:
    title: str
    link: str
    source: str
    category: str
    published: datetime  # always timezone-aware (UTC)
    summary: str = ""
    # Filled in during ranking:
    cluster_id: int = -1

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "category": self.category,
            "published": self.published.isoformat(),
            "summary": self.summary,
        }


@dataclass
class FetchResult:
    articles: list[Article] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (feed name, message)


def _parse_date(text: str | None) -> datetime:
    """Parse an RSS (RFC 822) or Atom (ISO 8601) date into aware UTC.

    Falls back to 'now' when the date is missing or unparseable so the article
    is still usable (it simply won't get a recency boost).
    """
    if text:
        text = text.strip()
        # RSS pubDate, e.g. "Mon, 23 Jun 2026 14:00:00 GMT"
        try:
            dt = parsedate_to_datetime(text)
            if dt is not None:
                return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, IndexError):
            pass
        # Atom updated/published, e.g. "2026-06-23T14:00:00Z"
        try:
            iso = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso)
            return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _tag(elem: ET.Element) -> str:
    """Local tag name without namespace, lowercased."""
    return elem.tag.rsplit("}", 1)[-1].lower()


def _find_text(item: ET.Element, *names: str) -> str:
    """First non-empty text among children whose local name matches `names`."""
    wanted = {n.lower() for n in names}
    for child in item:
        if _tag(child) in wanted and child.text and child.text.strip():
            return child.text.strip()
    return ""


def _find_link(item: ET.Element) -> str:
    """Extract a link from an RSS <link>text or an Atom <link href=...>."""
    for child in item:
        if _tag(child) != "link":
            continue
        if child.text and child.text.strip():  # RSS style
            return child.text.strip()
        href = child.attrib.get("href")  # Atom style
        if href:
            # Prefer the alternate/default link if multiple are present.
            rel = child.attrib.get("rel", "alternate")
            if rel == "alternate":
                return href.strip()
    # Fallback: any link href at all.
    for child in item:
        if _tag(child) == "link" and child.attrib.get("href"):
            return child.attrib["href"].strip()
    return ""


def parse_feed(data: bytes, feed: Feed) -> list[Article]:
    """Parse raw feed bytes (RSS or Atom) into Articles."""
    root = ET.fromstring(data)
    articles: list[Article] = []
    # RSS items are <item>; Atom entries are <entry>. Search the whole tree so
    # we don't have to care about channel nesting or namespaces.
    items = [e for e in root.iter() if _tag(e) in ("item", "entry")]
    for item in items:
        title = _find_text(item, "title")
        if not title:
            continue
        link = _find_link(item)
        published = _parse_date(
            _find_text(item, "pubDate", "published", "updated", "date")
        )
        summary = _find_text(item, "description", "summary")
        articles.append(
            Article(
                title=title,
                link=link,
                source=feed.name,
                category=feed.category,
                published=published,
                summary=summary,
            )
        )
    return articles


def fetch_feed(feed: Feed, timeout: int = 15) -> bytes:
    """Download a single feed's raw bytes."""
    req = urllib.request.Request(feed.url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_all(feeds: list[Feed], days: int = 7, timeout: int = 15) -> FetchResult:
    """Fetch every feed, parse it, and keep articles from the last `days`.

    Per-feed failures are collected in `result.errors` and never abort the run.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = FetchResult()
    seen_links: set[str] = set()
    for feed in feeds:
        try:
            raw = fetch_feed(feed, timeout=timeout)
            articles = parse_feed(raw, feed)
        except (urllib.error.URLError, ET.ParseError, ValueError, OSError) as exc:
            result.errors.append((feed.name, str(exc)))
            continue
        kept = 0
        for art in articles:
            if art.published < cutoff:
                continue
            # De-dupe identical links across feeds (e.g. syndicated copies).
            key = art.link or f"{art.source}:{art.title}"
            if key in seen_links:
                continue
            seen_links.add(key)
            result.articles.append(art)
            kept += 1
        if kept == 0 and not articles:
            result.errors.append((feed.name, "no articles parsed"))
    return result
