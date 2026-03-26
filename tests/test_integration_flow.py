from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weekly_journal_digest.cli import main


class IntegrationFlowTests(unittest.TestCase):
    def test_collect_and_build_weekly_digest_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            config_path = repo / "sources.yaml"
            config_path.write_text(
                """
timezone: America/Chicago
default_lookback_days: 28
state_dir: .state
social_science_keywords: ["political"]
sources:
  - id: source-a
    journal: Test Journal
    category: political_science
    adapter: crossref
    issns: ["0000-0000"]
    allowed_article_types: ["journal-article"]
""".strip(),
                encoding="utf-8",
            )

            class FakeAdapter:
                def collect(self, source, start_date, end_date):
                    from weekly_journal_digest.models import ArticleRecord

                    return [
                        ArticleRecord(
                            source_id=source.id,
                            journal=source.journal,
                            title="Weekly article",
                            published_date="2026-03-27",
                            canonical_url="https://doi.org/weekly",
                        ),
                        ArticleRecord(
                            source_id=source.id,
                            journal=source.journal,
                            title="Weekly article",
                            published_date="2026-03-27",
                            canonical_url="https://doi.org/weekly",
                        ),
                    ]

            with patch("weekly_journal_digest.cli.build_adapter_registry", return_value={"crossref": FakeAdapter()}):
                rc = main(["collect", "--config", str(config_path)])
                self.assertEqual(rc, 0)
                rc = main(["collect", "--config", str(config_path)])
                self.assertEqual(rc, 0)
                output_path = repo / "candidate.json"
                rc = main(
                    [
                        "build-weekly-digest",
                        "--config",
                        str(config_path),
                        "--digest-date",
                        "2026-03-30",
                        "--output",
                        str(output_path),
                    ]
                )
                self.assertEqual(rc, 0)
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["sections"]["new_this_week"]), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
