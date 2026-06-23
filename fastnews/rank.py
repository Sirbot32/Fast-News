"""Rank stories by cross-source coverage.

The core idea: a story carried by many independent outlets is more important
than one carried by a single outlet. We group near-duplicate headlines into
clusters, then score each cluster mostly by how many distinct sources cover it,
with a small recency boost so fresh news edges out week-old news of equal reach.
"""

from __future__ import annotations

import re
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher

from .fetch import Article

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "at",
    "by", "with", "from", "as", "is", "are", "was", "were", "be", "been", "it",
    "its", "this", "that", "these", "those", "his", "her", "their", "they",
    "he", "she", "we", "you", "i", "new", "says", "say", "said", "after",
    "over", "into", "out", "up", "down", "amid", "how", "why", "what", "who",
    "will", "has", "have", "had", "not", "no", "yes", "more", "than", "about",
    "us", "uk",
}

_WORD_RE = re.compile(r"[a-z0-9]+")

# Strip a trailing source attribution like " - BBC News" or " | The Guardian".
_SOURCE_SUFFIX_RE = re.compile(r"\s*[-–|]\s*[^-–|]{1,40}$")


def normalize(title: str) -> str:
    t = title.strip()
    t = _SOURCE_SUFFIX_RE.sub("", t)
    return t.strip()


def tokenize(title: str) -> set[str]:
    words = _WORD_RE.findall(normalize(title).lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _overlap(a: set[str], b: set[str]) -> float:
    """Overlap coefficient: |A∩B| / min(|A|,|B|).

    Better than Jaccard for headlines, where two outlets describe the same
    event but pad it with different extra words. Only trusted when at least two
    significant words are shared, to avoid merging on a single common term.
    """
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter < 2:
        return 0.0
    return inter / min(len(a), len(b))


def similarity(a: Article, b: Article) -> float:
    """0..1 similarity between two headlines."""
    ta, tb = tokenize(a.title), tokenize(b.title)
    if not (ta & tb):  # no shared significant word -> definitely different
        return 0.0
    jac = _jaccard(ta, tb)
    ratio = SequenceMatcher(None, normalize(a.title).lower(),
                            normalize(b.title).lower()).ratio()
    # Overlap is discounted so it must be high (≈0.6+) to cross typical
    # thresholds — it widens recall without merging loosely related stories.
    overlap = 0.85 * _overlap(ta, tb)
    return max(jac, ratio, overlap)


@dataclass
class Cluster:
    id: int
    articles: list[Article] = field(default_factory=list)
    score: float = 0.0

    @property
    def sources(self) -> list[str]:
        # Distinct sources, preserving first-seen order.
        seen, out = set(), []
        for a in self.articles:
            if a.source not in seen:
                seen.add(a.source)
                out.append(a.source)
        return out

    @property
    def source_count(self) -> int:
        return len(self.sources)

    @property
    def latest(self) -> datetime:
        return max(a.published for a in self.articles)

    @property
    def representative(self) -> Article:
        """Pick the headline most central to the cluster (highest total
        similarity to the others), tie-broken by recency."""
        if len(self.articles) == 1:
            return self.articles[0]
        best, best_key = self.articles[0], (-1.0, self.articles[0].published)
        for a in self.articles:
            total = sum(similarity(a, b) for b in self.articles if b is not a)
            key = (total, a.published)
            if key > best_key:
                best, best_key = a, key
        return best

    @property
    def categories(self) -> list[str]:
        seen, out = set(), []
        for a in self.articles:
            if a.category not in seen:
                seen.add(a.category)
                out.append(a.category)
        return out


def cluster_articles(articles: list[Article], threshold: float = 0.5) -> list[Cluster]:
    """Greedy single-pass clustering by headline similarity.

    Each article joins the existing cluster it best matches (above threshold),
    compared against that cluster's representative-so-far; otherwise it starts a
    new cluster. Good enough and fast for the volumes a news front page sees.
    """
    clusters: list[Cluster] = []
    for art in articles:
        best_cluster, best_sim = None, threshold
        for cl in clusters:
            # Match against the closest existing member so a story can attach
            # via any of its phrasings, not just the cluster's first headline.
            sim = max(similarity(art, member) for member in cl.articles)
            if sim >= best_sim:
                best_cluster, best_sim = cl, sim
        if best_cluster is None:
            cl = Cluster(id=len(clusters))
            cl.articles.append(art)
            clusters.append(cl)
        else:
            best_cluster.articles.append(art)
    for cl in clusters:
        for a in cl.articles:
            a.cluster_id = cl.id
    return clusters


def score_clusters(clusters: list[Cluster], now: datetime | None = None) -> list[Cluster]:
    """Importance = coverage (distinct sources) with a mild recency boost.

    coverage dominates: 2 sources clearly beat 1. Recency only separates
    stories of equal reach. Score is otherwise monotonic in source_count.
    """
    now = now or datetime.now(timezone.utc)
    for cl in clusters:
        coverage = cl.source_count
        age_hours = max(0.0, (now - cl.latest).total_seconds() / 3600.0)
        # Decays from ~1.0 (now) toward 0 over a few days; always < 1 so it can
        # never let a lower-coverage story leapfrog a higher-coverage one.
        recency = math.exp(-age_hours / 72.0)
        cl.score = coverage + 0.9 * recency
    clusters.sort(key=lambda c: (c.score, c.latest), reverse=True)
    return clusters


def rank(articles: list[Article], threshold: float = 0.5,
         now: datetime | None = None) -> list[Cluster]:
    return score_clusters(cluster_articles(articles, threshold), now=now)
