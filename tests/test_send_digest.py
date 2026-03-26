from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weekly_journal_digest.cli import main


class SendDigestTests(unittest.TestCase):
    def test_send_digest_writes_once_without_duplicate_resend(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            config_path = repo / "sources.yaml"
            config_path.write_text(
                """
timezone: America/Chicago
default_lookback_days: 28
state_dir: .state
social_science_keywords: []
sources: []
""".strip(),
                encoding="utf-8",
            )
            reviewed_path = repo / "reviewed.md"
            reviewed_path.write_text("Subject: Test digest\n\nHello world.", encoding="utf-8")
            sent = []

            class FakeSender:
                @classmethod
                def from_env(cls):
                    return cls()

                def send_markdown(self, to_address, subject, markdown_body):
                    sent.append((to_address, subject, markdown_body))
                    return "message-1"

            with patch("weekly_journal_digest.cli.GmailSender", FakeSender):
                rc = main(
                    [
                        "send-digest",
                        "--config",
                        str(config_path),
                        "--digest-date",
                        "2026-03-30",
                        "--reviewed-digest",
                        str(reviewed_path),
                        "--recipient",
                        "reader@example.com",
                    ]
                )
                self.assertEqual(rc, 0)
                rc = main(
                    [
                        "send-digest",
                        "--config",
                        str(config_path),
                        "--digest-date",
                        "2026-03-30",
                        "--reviewed-digest",
                        str(reviewed_path),
                        "--recipient",
                        "reader@example.com",
                    ]
                )
                self.assertEqual(rc, 0)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0][1], "Test digest")

    def test_send_digest_uses_html_summary_and_pdf_attachment_when_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            config_path = repo / "sources.yaml"
            config_path.write_text(
                """
timezone: America/Chicago
default_lookback_days: 28
state_dir: .state
social_science_keywords: []
sources: []
""".strip(),
                encoding="utf-8",
            )
            reviewed_path = repo / "reviewed.md"
            reviewed_path.write_text(
                """Subject: Test digest

## Email Summary

Short summary.

## Collection Snapshot

- Total collected candidates: 10
- New This Week candidates: 6
- Previous Week Catch-Up candidates: 3
- Late Additions candidates: 1
- Curated digest below: 2 new, 1 catch-up, 0 late additions

## Highlights

- **Important article**
  Journal: Nature Human Behaviour
  Published: 2026-03-28
  Why it matters: It is directly relevant to the weekly reading list.
  Link: https://doi.org/example

## Full Curated Digest

### New This Week

#### Nature Human Behaviour
- **Important article**
  Published: 2026-03-28
  Link: https://doi.org/example
  Abstract: Example abstract.
""",
                encoding="utf-8",
            )
            sent = []

            class FakeSender:
                @classmethod
                def from_env(cls):
                    return cls()

                def send_markdown(self, to_address, subject, markdown_body):
                    raise AssertionError("legacy plain-text path should not be used")

                def send_digest_package(self, to_address, subject, plain_text_body, html_body, attachments):
                    sent.append((to_address, subject, plain_text_body, html_body, attachments))
                    return "message-2"

            with patch("weekly_journal_digest.cli.GmailSender", FakeSender):
                rc = main(
                    [
                        "send-digest",
                        "--config",
                        str(config_path),
                        "--digest-date",
                        "2026-03-30",
                        "--reviewed-digest",
                        str(reviewed_path),
                        "--recipient",
                        "reader@example.com",
                    ]
                )
                self.assertEqual(rc, 0)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0][1], "Test digest")
            self.assertIn("The full curated digest is attached as a PDF.", sent[0][2])
            self.assertIn("Open article", sent[0][3])
            self.assertEqual(len(sent[0][4]), 1)
            self.assertEqual(sent[0][4][0].filename, "reviewed.pdf")
            self.assertTrue((repo / "reviewed.pdf").exists())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
