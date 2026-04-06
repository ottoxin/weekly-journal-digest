from __future__ import annotations

import io
import socket
import unittest
from urllib.error import URLError
from unittest.mock import patch

from weekly_journal_digest.http_client import (
    JsonHttpClient,
    NETWORK_RETRY_ATTEMPTS,
    TransientHttpError,
)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class JsonHttpClientRetryTests(unittest.TestCase):
    def test_get_json_retries_transient_dns_error(self) -> None:
        client = JsonHttpClient()
        with (
            patch(
                "weekly_journal_digest.http_client.urlopen",
                side_effect=[
                    URLError(socket.gaierror("nodename nor servname provided, or not known")),
                    _FakeResponse(b'{"status": "ok"}'),
                ],
            ) as urlopen_mock,
            patch("weekly_journal_digest.http_client.time.sleep") as sleep_mock,
        ):
            payload = client.get_json("https://example.com/items")

        self.assertEqual(payload, {"status": "ok"})
        self.assertEqual(urlopen_mock.call_count, 2)
        self.assertEqual(sleep_mock.call_count, 1)

    def test_post_json_raises_after_retry_budget_exhausted(self) -> None:
        client = JsonHttpClient()
        with (
            patch(
                "weekly_journal_digest.http_client.urlopen",
                side_effect=URLError(socket.gaierror("Temporary failure in name resolution")),
            ),
            patch("weekly_journal_digest.http_client.time.sleep") as sleep_mock,
        ):
            with self.assertRaises(TransientHttpError) as ctx:
                client.post_json("https://example.com/items", {"key": "value"})

        self.assertIn("HTTP POST https://example.com/items", str(ctx.exception))
        self.assertEqual(sleep_mock.call_count, NETWORK_RETRY_ATTEMPTS - 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
