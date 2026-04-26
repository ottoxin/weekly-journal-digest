from __future__ import annotations

import contextlib
import io
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from weekly_journal_digest.cli import main
from weekly_journal_digest.emailing import GmailTransientNetworkError
from weekly_journal_digest.storage import StateStore


class SendDigestTests(unittest.TestCase):
    def _run_git(self, repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=check,
            capture_output=True,
            text=True,
        )

    def _init_git_repo(self, repo: Path) -> Path:
        remote = repo.parent / f"{repo.name}-remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(remote)],
            check=True,
            capture_output=True,
            text=True,
        )
        self._run_git(repo, "init")
        self._run_git(repo, "branch", "-M", "main")
        self._run_git(repo, "config", "user.email", "tests@example.com")
        self._run_git(repo, "config", "user.name", "Digest Test")
        return remote

    def test_send_digest_uses_configured_recipients_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            config_dir = repo / "config"
            config_dir.mkdir()
            config_path = config_dir / "sources.yaml"
            config_path.write_text(
                """
timezone: America/Chicago
default_lookback_days: 28
state_dir: .state
recipients_file: config/recipients.json
social_science_keywords: []
sources: []
""".strip(),
                encoding="utf-8",
            )
            (config_dir / "recipients.json").write_text(
                """
{
  "recipients": [
    {"email": "first@example.com", "name": "Ada Lovelace", "active": true},
    {"email": "second@example.com", "active": true},
    {"email": "inactive@example.com", "active": false}
  ]
}
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
                    return f"message-{len(sent)}"

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
                    ]
                )
                self.assertEqual(rc, 0)
            self.assertEqual(
                [item[0] for item in sent],
                ["first@example.com", "second@example.com"],
            )
            self.assertTrue(sent[0][2].startswith("Dear Ada Lovelace,\n\n"))
            self.assertIn("COMAP Journal Bot", sent[0][2])
            self.assertTrue(
                sent[0][2].rstrip().endswith(
                    "If you wish to unsubscribe, send email to haohangxin@u.northwestern.edu"
                )
            )
            self.assertTrue(sent[1][2].startswith("Dear Second,\n\n"))

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
            self.assertIn("Dear Reader,", sent[0][2])
            self.assertIn("The full curated digest is attached as a PDF.", sent[0][2])
            self.assertIn("COMAP Journal Bot", sent[0][2])
            self.assertIn("If you wish to unsubscribe, send email to haohangxin@u.northwestern.edu", sent[0][2])
            self.assertIn("Dear Reader,", sent[0][3])
            self.assertIn("COMAP Journal Bot</div>", sent[0][3])
            self.assertIn("If you wish to unsubscribe, send email to haohangxin@u.northwestern.edu", sent[0][3])
            self.assertIn("Open article", sent[0][3])
            self.assertEqual(len(sent[0][4]), 1)
            self.assertEqual(sent[0][4][0].filename, "reviewed.pdf")
            self.assertTrue((repo / "reviewed.pdf").exists())

    def test_render_digest_writes_preview_artifacts_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            reviewed_path = repo / "reviewed.md"
            reviewed_path.write_text(
                """Subject: Test digest

## Summary

Short summary.

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
            output_dir = repo / "preview"
            with patch(
                "weekly_journal_digest.cli.GmailSender.from_env",
                side_effect=AssertionError("render-digest must not initialize Gmail"),
            ):
                rc = main(
                    [
                        "render-digest",
                        "--reviewed-digest",
                        str(reviewed_path),
                        "--output-dir",
                        str(output_dir),
                        "--recipient-name",
                        "Haohang Xin",
                    ]
                )
            self.assertEqual(rc, 0)
            text_path = output_dir / "reviewed.preview.txt"
            html_path = output_dir / "reviewed.preview.html"
            pdf_path = output_dir / "reviewed.preview.pdf"
            self.assertTrue(text_path.exists())
            self.assertTrue(html_path.exists())
            self.assertTrue(pdf_path.exists())
            self.assertIn("Subject: Test digest", text_path.read_text(encoding="utf-8"))
            self.assertIn("Dear Haohang Xin,", text_path.read_text(encoding="utf-8"))
            self.assertIn("Dear Haohang Xin,", html_path.read_text(encoding="utf-8"))
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF-"))
            self.assertFalse((repo / ".state").exists())

    def test_send_digest_uses_configured_recipient_name_in_greeting(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            config_dir = repo / "config"
            config_dir.mkdir()
            config_path = config_dir / "sources.yaml"
            config_path.write_text(
                """
timezone: America/Chicago
default_lookback_days: 28
state_dir: .state
recipients_file: config/recipients.json
social_science_keywords: []
sources: []
""".strip(),
                encoding="utf-8",
            )
            (config_dir / "recipients.json").write_text(
                """
{
  "recipients": [
    {"email": "reader@example.com", "name": "Haohang Xin", "active": true}
  ]
}
""".strip(),
                encoding="utf-8",
            )
            reviewed_path = repo / "reviewed.md"
            reviewed_path.write_text(
                """Subject: Test digest

## Summary

Short summary.

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

                def send_digest_package(self, to_address, subject, plain_text_body, html_body, attachments):
                    sent.append((to_address, subject, plain_text_body, html_body))
                    return "message-3"

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
                    ]
                )
            self.assertEqual(rc, 0)
            self.assertEqual(len(sent), 1)
            self.assertIn("Dear Haohang Xin,", sent[0][2])
            self.assertIn("Dear Haohang Xin,", sent[0][3])
            self.assertIn("If you wish to unsubscribe, send email to haohangxin@u.northwestern.edu", sent[0][2])
            self.assertIn("If you wish to unsubscribe, send email to haohangxin@u.northwestern.edu", sent[0][3])

    def test_send_digest_auto_commits_and_pushes_log_files_when_repo_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            remote = self._init_git_repo(repo)
            (repo / ".gitignore").write_text(".state/\n", encoding="utf-8")
            config_dir = repo / "config"
            config_dir.mkdir()
            config_path = config_dir / "sources.yaml"
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
            self._run_git(repo, "add", ".gitignore", "config/sources.yaml")
            self._run_git(repo, "commit", "-m", "Initial commit")
            self._run_git(repo, "remote", "add", "origin", str(remote))
            self._run_git(repo, "push", "-u", "origin", "main")

            log_dir = repo / "logs" / "2026-03-30"
            log_dir.mkdir(parents=True)
            (log_dir / "candidate_digest-2026-03-30.json").write_text("{}", encoding="utf-8")
            reviewed_path = log_dir / "reviewed_digest-2026-03-30.structured.md"
            reviewed_path.write_text(
                """Subject: Test digest

## Summary

Short summary.

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

            class FakeSender:
                @classmethod
                def from_env(cls):
                    return cls()

                def send_digest_package(self, to_address, subject, plain_text_body, html_body, attachments):
                    return "message-4"

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
                        "otto@example.com",
                    ]
                )
                self.assertEqual(rc, 0)

            latest_commit = self._run_git(repo, "log", "-1", "--format=%s").stdout.strip()
            self.assertEqual(latest_commit, "Add digest log for 2026-03-30")
            remote_commit = subprocess.run(
                ["git", f"--git-dir={remote}", "log", "-1", "--format=%s", "main"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(remote_commit, "Add digest log for 2026-03-30")
            status = self._run_git(repo, "status", "--short").stdout.strip()
            self.assertEqual(status, "")

    def test_send_digest_skips_auto_commit_when_repo_has_unrelated_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            remote = self._init_git_repo(repo)
            (repo / ".gitignore").write_text(".state/\n", encoding="utf-8")
            config_dir = repo / "config"
            config_dir.mkdir()
            config_path = config_dir / "sources.yaml"
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
            self._run_git(repo, "add", ".gitignore", "config/sources.yaml")
            self._run_git(repo, "commit", "-m", "Initial commit")
            self._run_git(repo, "remote", "add", "origin", str(remote))
            self._run_git(repo, "push", "-u", "origin", "main")

            (repo / "notes.txt").write_text("unrelated change\n", encoding="utf-8")
            log_dir = repo / "logs" / "2026-03-30"
            log_dir.mkdir(parents=True)
            (log_dir / "candidate_digest-2026-03-30.json").write_text("{}", encoding="utf-8")
            reviewed_path = log_dir / "reviewed_digest-2026-03-30.structured.md"
            reviewed_path.write_text(
                """Subject: Test digest

## Summary

Short summary.

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

            class FakeSender:
                @classmethod
                def from_env(cls):
                    return cls()

                def send_digest_package(self, to_address, subject, plain_text_body, html_body, attachments):
                    return "message-5"

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
                        "otto@example.com",
                    ]
                )
                self.assertEqual(rc, 0)

            latest_commit = self._run_git(repo, "log", "-1", "--format=%s").stdout.strip()
            self.assertEqual(latest_commit, "Initial commit")
            status = self._run_git(repo, "status", "--short").stdout
            self.assertIn("notes.txt", status)
            remote_commit = subprocess.run(
                ["git", f"--git-dir={remote}", "log", "-1", "--format=%s", "main"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.assertEqual(remote_commit, "Initial commit")

    def test_send_digest_returns_clean_error_without_record_when_sender_init_fails(self) -> None:
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
            stderr = io.StringIO()

            with (
                patch(
                    "weekly_journal_digest.cli.GmailSender.from_env",
                    side_effect=GmailTransientNetworkError(
                        "Google OAuth credential refresh",
                        4,
                        socket.gaierror("Temporary failure in name resolution"),
                    ),
                ),
                contextlib.redirect_stderr(stderr),
            ):
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

            self.assertEqual(rc, 1)
            self.assertIn("No send record was written", stderr.getvalue())
            store = StateStore(repo / ".state" / "digest.db")
            self.assertFalse(store.has_sent_digest("2026-03-30", "reader@example.com"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
