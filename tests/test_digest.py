from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from weekly_journal_digest.digest import build_candidate_digest, compute_weekly_windows
from weekly_journal_digest.models import AppConfig, ArticleRecord
from weekly_journal_digest.storage import StateStore


class DigestTests(unittest.TestCase):
    def test_compute_weekly_windows_uses_previous_complete_week(self) -> None:
        windows = compute_weekly_windows(date(2026, 3, 30))
        self.assertEqual(windows.new_this_week_start, "2026-03-23")
        self.assertEqual(windows.new_this_week_end, "2026-03-29")
        self.assertEqual(windows.previous_week_start, "2026-03-16")
        self.assertEqual(windows.previous_week_end, "2026-03-22")

    def test_build_candidate_digest_classifies_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(Path(tmpdir) / "digest.db")
            seen_at = datetime(2026, 3, 30, 14, 0, tzinfo=timezone.utc).isoformat()
            store.upsert_articles(
                [
                    ArticleRecord(
                        source_id="joc",
                        journal="Journal of Communication",
                        title="Current week article",
                        published_date="2026-03-27",
                        canonical_url="https://doi.org/current",
                        doi="10.1000/current",
                        authors=["Jane Doe", "John Smith"],
                        affiliations=["Northwestern University", "COMAP Lab"],
                        abstract="Current abstract.",
                    ),
                    ArticleRecord(
                        source_id="apsr",
                        journal="American Political Science Review",
                        title="Previous week article",
                        published_date="2026-03-18",
                        canonical_url="https://doi.org/previous",
                    ),
                    ArticleRecord(
                        source_id="nature",
                        journal="Nature",
                        title="Late addition",
                        published_date="2026-03-01",
                        canonical_url="https://doi.org/late",
                    ),
                ],
                seen_at=seen_at,
            )
            config = AppConfig(
                timezone="America/Chicago",
                default_lookback_days=28,
                state_dir=".state",
                social_science_keywords=[],
                sources=[],
            )
            payload = build_candidate_digest(
                store,
                config,
                date(2026, 3, 30),
                Path(tmpdir) / "candidate.json",
                generated_at=datetime(2026, 3, 30, 14, 0, tzinfo=timezone.utc),
            )
            self.assertEqual(len(payload["sections"]["new_this_week"]), 1)
            self.assertEqual(len(payload["sections"]["previous_week_catch_up"]), 1)
            self.assertEqual(len(payload["sections"]["late_additions"]), 1)
            self.assertEqual(payload["sections"]["new_this_week"][0]["doi"], "10.1000/current")
            self.assertEqual(payload["sections"]["new_this_week"][0]["authors"], ["Jane Doe", "John Smith"])
            self.assertEqual(
                payload["sections"]["new_this_week"][0]["affiliations"],
                ["Northwestern University", "COMAP Lab"],
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
