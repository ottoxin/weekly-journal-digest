from __future__ import annotations

import unittest

from weekly_journal_digest.normalize import (
    choose_best_abstract,
    clean_abstract,
    make_dedupe_key,
    normalize_doi,
)


class NormalizeTests(unittest.TestCase):
    def test_normalize_doi_strips_prefix(self) -> None:
        self.assertEqual(normalize_doi("https://doi.org/10.1000/ABC"), "10.1000/abc")

    def test_clean_abstract_removes_tags(self) -> None:
        self.assertEqual(clean_abstract("<jats:p>Hello <b>world</b></jats:p>"), "Hello world")

    def test_choose_best_abstract_prefers_primary(self) -> None:
        self.assertEqual(choose_best_abstract("Primary", "Fallback"), "Primary")

    def test_make_dedupe_key_falls_back_without_doi(self) -> None:
        key = make_dedupe_key(None, None, "Journal", "Article", "2026-03-25")
        self.assertTrue(key.startswith("fallback:"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
