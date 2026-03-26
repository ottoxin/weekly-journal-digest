from __future__ import annotations

import unittest

from weekly_journal_digest.filters import matches_social_science, should_include_record
from weekly_journal_digest.models import ArticleRecord, SourceConfig


class FilterTests(unittest.TestCase):
    def test_social_science_match_uses_title_and_abstract(self) -> None:
        article = ArticleRecord(
            source_id="nature",
            journal="Nature",
            title="Political behavior in online networks",
            abstract="A communication study of voters.",
            published_date="2026-03-25",
        )
        self.assertTrue(matches_social_science(article, ["political", "communication"]))

    def test_should_exclude_correction_title(self) -> None:
        source = SourceConfig(id="joc", journal="Journal of Communication", category="communication", adapter="crossref")
        article = ArticleRecord(
            source_id="joc",
            journal="Journal of Communication",
            title="Correction to: Some article",
            published_date="2026-03-25",
        )
        self.assertEqual(should_include_record(source, article, [])[0], False)

    def test_general_science_requires_social_science_match(self) -> None:
        source = SourceConfig(
            id="nature",
            journal="Nature",
            category="general_science",
            adapter="crossref",
            require_social_science_match=True,
        )
        article = ArticleRecord(
            source_id="nature",
            journal="Nature",
            title="Quantum materials update",
            abstract="A materials science paper.",
            published_date="2026-03-25",
        )
        include, reason = should_include_record(source, article, ["political"])
        self.assertFalse(include)
        self.assertEqual(reason, "not-social-science-related")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
