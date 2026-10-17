from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from weekly_journal_digest.cli import main
from weekly_journal_digest.models import ArticleRecord
from weekly_journal_digest.reviewed_digest import parse_reviewed_digest, render_curated_digest_pdf
from weekly_journal_digest.storage import StateStore
from weekly_journal_digest.validation import validate_reviewed_digest


EMPTY = """Subject: Weekly journal digest for 2026-08-31 to 2026-09-06

## Summary
No qualifying articles for 2026-08-31 to 2026-09-06.

## Highlights

## Full Curated Digest
No qualifying articles.
"""
ARTICLE = """### New This Week
#### Test Journal
- **Political article**
  Published: 2026-09-02
  Authors: Ada
  DOI: 10.1000/test
  Link: https://doi.org/10.1000/test
  Abstract: Actual abstract.
"""


class WorkflowGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.config = self.repo / "sources.yaml"
        self.config.write_text("""timezone: America/Chicago
state_dir: .state
sources:
  - id: test
    journal: Test Journal
    category: political_science
    adapter: crossref
""")
        self.reviewed = self.repo / "reviewed.md"
        self.reviewed.write_text(EMPTY)
        self.args = ["send-digest", "--config", str(self.config), "--digest-date", "2026-09-07",
                     "--reviewed-digest", str(self.reviewed), "--full-html"]

    def test_test_send_is_isolated_and_idempotent(self):
        sender = MagicMock()
        sender.send_digest_package.return_value = "test-message"
        store = StateStore(self.repo / ".state/digest.db")
        store.record_sent_digest("2026-09-07", "otto@example.com", "original", "original", "2026-09-05", "production-message")
        with patch("weekly_journal_digest.cli.GmailSender.from_env", return_value=sender), patch("weekly_journal_digest.cli.maybe_commit_and_push_log_artifacts") as publish:
            args = self.args + ["--test", "--recipient", "otto@example.com"]
            self.assertEqual(main(args), 0)
            self.assertEqual(main(args), 0)
            publish.assert_not_called()
        sender.send_digest_package.assert_called_once()
        self.assertTrue(sender.send_digest_package.call_args.args[1].startswith("[TEST]"))
        self.assertEqual(len(sender.send_digest_package.call_args.args[4]), 2)
        self.assertTrue(store.has_sent_digest("test:2026-09-07", "otto@example.com"))
        with store._connect() as connection:
            row = connection.execute("SELECT message_id FROM sent_digests WHERE digest_key = '2026-09-07'").fetchone()
        self.assertEqual(row[0], "production-message")

    def test_test_requires_one_explicit_recipient(self):
        with patch("weekly_journal_digest.cli.GmailSender.from_env") as sender:
            for extra in [["--test"], ["--test", "--recipient", "a@example.com,b@example.com"]]:
                with self.assertRaises(ValueError):
                    main(self.args + extra)
            sender.assert_not_called()

    def test_malformed_structure_never_sends_legacy_email(self):
        self.reviewed.write_text(EMPTY.replace("## Highlights", "## Highlight"))
        with patch("weekly_journal_digest.cli.GmailSender.from_env") as sender:
            with self.assertRaisesRegex(ValueError, "Invalid structured"):
                main(self.args + ["--recipient", "otto@example.com"])
            sender.assert_not_called()

    def test_empty_digest_still_renders_pdf(self):
        reviewed = parse_reviewed_digest(EMPTY)
        self.assertIsNotNone(reviewed)
        self.assertEqual(reviewed.highlights, [])
        self.assertTrue(render_curated_digest_pdf(reviewed).startswith(b"%PDF"))

    def test_enrichment_failure_preserves_collected_article(self):
        adapter = MagicMock()
        adapter.collect.return_value = [ArticleRecord(source_id="test", journal="Test Journal", title="Political article", published_date="2026-09-02")]
        enricher = MagicMock()
        enricher.enrich_records.side_effect = RuntimeError("Unauthorized enrichment service")
        with patch("weekly_journal_digest.cli.build_adapter_registry", return_value={"crossref": adapter}), patch("weekly_journal_digest.cli.build_metadata_enricher", return_value=enricher):
            self.assertEqual(main(["collect", "--config", str(self.config), "--end-date", "2026-09-06"]), 0)
        store = StateStore(self.repo / ".state/digest.db")
        self.assertEqual(len(store.get_articles_between("2026-08-31", "2026-09-07")), 1)
        archive = json.loads(next((self.repo / ".state/archives").glob("*.json")).read_text())
        self.assertIn("Unauthorized", archive["sources"][0]["enrichment_error"])

    def test_validator_checks_membership_metadata_and_lost_entries(self):
        candidate = {"windows": {"new_this_week_start": "2026-08-31", "new_this_week_end": "2026-09-06"}, "sections": {
            "new_this_week": [{"journal": "Test Journal", "title": "Political article", "published_date": "2026-09-02", "authors": ["Ada"], "doi": "10.1000/test", "link": "https://doi.org/10.1000/test", "abstract": "Actual abstract."}],
            "previous_week_catch_up": [], "late_additions": []}}
        markdown = EMPTY.replace("## Full Curated Digest\nNo qualifying articles.", "## Full Curated Digest\n" + ARTICLE)
        self.assertEqual(validate_reviewed_digest(candidate, markdown), [])
        for broken in [markdown.replace("Actual abstract.", "Invented abstract."), markdown.replace("### New This Week", "### Late Additions"), markdown.replace("#### Test Journal\n", ""), markdown + ARTICLE, markdown.replace("Political article", "Invented article")]:
            self.assertTrue(validate_reviewed_digest(candidate, broken))


if __name__ == "__main__":
    unittest.main()
