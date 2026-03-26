from __future__ import annotations

import unittest

from weekly_journal_digest.models import ArticleRecord
from weekly_journal_digest.reconcile import reconcile_with_crossref


class ReconcileTests(unittest.TestCase):
    def test_reconcile_uses_crossref_when_primary_missing_fields(self) -> None:
        primary = ArticleRecord(
            source_id="nature",
            journal="Nature",
            title="Behavior and institutions",
            published_date="2026-03-25",
            abstract=None,
            canonical_url=None,
        )
        crossref = ArticleRecord(
            source_id="nature",
            journal="Nature",
            title="Behavior and institutions",
            published_date="2026-03-25",
            abstract="Crossref abstract",
            canonical_url="https://doi.org/10.1234/example",
            doi="10.1234/example",
            affiliations=["Northwestern University"],
            subjects=["Political Science"],
        )
        merged = reconcile_with_crossref(primary, crossref)
        self.assertEqual(merged.abstract, "Crossref abstract")
        self.assertEqual(merged.canonical_url, "https://doi.org/10.1234/example")
        self.assertEqual(merged.affiliations, ["Northwestern University"])
        self.assertIn("Political Science", merged.subjects)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
