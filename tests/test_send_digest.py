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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
