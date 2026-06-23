"""Smoke tests for clustering and scoring. Run: python3 -m unittest -v"""

import unittest
from datetime import datetime, timezone, timedelta

from fastnews.fetch import Article
from fastnews.rank import rank, similarity, tokenize


def _art(title, source, hours_ago=0, category="Top"):
    return Article(
        title=title, link=f"http://x/{source}/{abs(hash(title))}",
        source=source, category=category,
        published=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
    )


class TestTokenize(unittest.TestCase):
    def test_drops_stopwords_and_source_suffix(self):
        toks = tokenize("The bank raises rates - BBC News")
        self.assertIn("bank", toks)
        self.assertIn("rates", toks)
        self.assertNotIn("the", toks)
        self.assertNotIn("bbc", toks)  # suffix stripped


class TestSimilarity(unittest.TestCase):
    def test_same_story_different_wording_is_similar(self):
        a = _art("Central bank raises interest rates to tame inflation", "BBC")
        b = _art("Interest rates raised again by central bank", "Guardian")
        self.assertGreaterEqual(similarity(a, b), 0.5)

    def test_unrelated_stories_are_dissimilar(self):
        a = _art("Wildfires force evacuations across southern Europe", "BBC")
        b = _art("Tech giant unveils new AI assistant", "CNN")
        self.assertLess(similarity(a, b), 0.5)


class TestRank(unittest.TestCase):
    def test_coverage_drives_ranking(self):
        arts = [
            _art("Wildfires force evacuations across southern Europe", "BBC", 1),
            _art("Evacuations as wildfires spread across southern Europe", "CNN", 2),
            _art("Southern Europe wildfires prompt mass evacuations", "Guardian", 1),
            _art("Tech giant unveils new AI assistant", "CNN", 1),
        ]
        clusters = rank(arts)
        # The 3-source wildfire story must outrank the 1-source tech story.
        self.assertEqual(clusters[0].source_count, 3)
        self.assertGreater(clusters[0].score, clusters[-1].score)

    def test_recency_breaks_ties_at_equal_coverage(self):
        arts = [
            _art("Storm hits the coast", "BBC", 100),
            _art("Quake rattles the city", "CNN", 1),
        ]
        clusters = rank(arts)
        # Both single-source; the fresher one ranks first.
        self.assertEqual(clusters[0].representative.source, "CNN")


if __name__ == "__main__":
    unittest.main()
