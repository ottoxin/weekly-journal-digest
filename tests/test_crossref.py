from __future__ import annotations

import unittest
from datetime import date
from urllib.parse import parse_qs, urlparse

from weekly_journal_digest.crossref import CrossrefClient
from weekly_journal_digest.models import SourceConfig


class _RecordingHttpClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def get_json(self, url: str):
        self.urls.append(url)
        return {"message": {"items": []}}


class CrossrefClientTests(unittest.TestCase):
    def test_cursor_request_omits_incompatible_server_side_sorting(self) -> None:
        http_client = _RecordingHttpClient()
        client = CrossrefClient(http_client=http_client)
        source = SourceConfig(
            id="joc",
            journal="Journal of Communication",
            category="communication",
            adapter="crossref",
            issns=["0021-9916"],
        )

        records = client.fetch_source_records(
            source,
            date(2026, 8, 3),
            date(2026, 8, 30),
        )

        self.assertEqual(records, [])
        self.assertEqual(len(http_client.urls), 1)
        query = parse_qs(urlparse(http_client.urls[0]).query)
        self.assertEqual(query["cursor"], ["*"])
        self.assertNotIn("sort", query)
        self.assertNotIn("order", query)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
