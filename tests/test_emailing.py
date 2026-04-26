from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from google.auth.exceptions import RefreshError

from weekly_journal_digest.emailing import (
    GmailSender,
    GmailSettings,
    GmailTransientNetworkError,
    NETWORK_RETRY_ATTEMPTS,
)


class GmailSenderRetryTests(unittest.TestCase):
    def test_build_service_retries_transient_refresh_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text("{}", encoding="utf-8")
            settings = GmailSettings(
                credentials_file=Path(tmpdir) / "credentials.json",
                token_file=token_path,
            )
            sender = GmailSender(settings)

            class FakeCredentials:
                valid = False
                expired = True
                refresh_token = "refresh-token"

                def __init__(self) -> None:
                    self.calls = 0

                def refresh(self, request) -> None:
                    self.calls += 1
                    if self.calls == 1:
                        raise socket.gaierror("Temporary failure in name resolution")

                def to_json(self) -> str:
                    return '{"token": "ok"}'

            creds = FakeCredentials()

            with (
                patch(
                    "weekly_journal_digest.emailing.Credentials.from_authorized_user_file",
                    return_value=creds,
                ),
                patch("weekly_journal_digest.emailing.build", return_value="service") as build_mock,
                patch("weekly_journal_digest.emailing.time.sleep") as sleep_mock,
            ):
                service = sender._build_service()

            self.assertEqual(service, "service")
            self.assertEqual(creds.calls, 2)
            self.assertEqual(build_mock.call_count, 1)
            self.assertEqual(sleep_mock.call_count, 1)
            self.assertEqual(token_path.read_text(encoding="utf-8"), '{"token": "ok"}')

    def test_build_service_raises_after_retry_budget_exhausted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text("{}", encoding="utf-8")
            settings = GmailSettings(
                credentials_file=Path(tmpdir) / "credentials.json",
                token_file=token_path,
            )
            sender = GmailSender(settings)

            class FakeCredentials:
                valid = False
                expired = True
                refresh_token = "refresh-token"

                def refresh(self, request) -> None:
                    raise socket.gaierror("Temporary failure in name resolution")

                def to_json(self) -> str:
                    return '{"token": "stale"}'

            with (
                patch(
                    "weekly_journal_digest.emailing.Credentials.from_authorized_user_file",
                    return_value=FakeCredentials(),
                ),
                patch("weekly_journal_digest.emailing.time.sleep") as sleep_mock,
            ):
                with self.assertRaises(GmailTransientNetworkError) as ctx:
                    sender._build_service()

            self.assertIn("Google OAuth credential refresh", str(ctx.exception))
            self.assertEqual(sleep_mock.call_count, NETWORK_RETRY_ATTEMPTS - 1)

    def test_invalid_grant_starts_fresh_oauth_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text("{}", encoding="utf-8")
            settings = GmailSettings(
                credentials_file=Path(tmpdir) / "credentials.json",
                token_file=token_path,
            )
            sender = GmailSender(settings)

            class ExpiredCredentials:
                valid = False
                expired = True
                refresh_token = "revoked-refresh-token"

                def refresh(self, request) -> None:
                    raise RefreshError(
                        "invalid_grant: Token has been expired or revoked.",
                        {"error": "invalid_grant"},
                    )

            class FreshCredentials:
                def to_json(self) -> str:
                    return '{"token": "fresh"}'

            class FakeFlow:
                def __init__(self) -> None:
                    self.calls = 0

                def run_local_server(self, port: int = 0):
                    self.calls += 1
                    return FreshCredentials()

            flow = FakeFlow()

            with (
                patch(
                    "weekly_journal_digest.emailing.Credentials.from_authorized_user_file",
                    return_value=ExpiredCredentials(),
                ),
                patch(
                    "weekly_journal_digest.emailing.InstalledAppFlow.from_client_secrets_file",
                    return_value=flow,
                ),
                patch("weekly_journal_digest.emailing.build", return_value="service") as build_mock,
            ):
                service = sender._build_service()

            self.assertEqual(service, "service")
            self.assertEqual(flow.calls, 1)
            self.assertEqual(build_mock.call_count, 1)
            self.assertEqual(token_path.read_text(encoding="utf-8"), '{"token": "fresh"}')


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
