from __future__ import annotations

import unittest
from unittest.mock import Mock
from urllib.error import HTTPError

from weekly_journal_digest.enrichment import (
    MetadataEnricher,
    OpenAlexClient,
    SemanticScholarClient,
)
from weekly_journal_digest.models import ArticleRecord


class FakeHttpClient:
    def __init__(self, get_responses=None, post_responses=None):
        self.get_responses = get_responses or {}
        self.post_responses = post_responses or {}

    def get_json(self, url, headers=None):
        response = self.get_responses.get(url)
        if response is None:
            raise AssertionError(f"Unexpected GET {url}")
        return response

    def post_json(self, url, payload, headers=None):
        response = self.post_responses.get(url)
        if response is None:
            raise AssertionError(f"Unexpected POST {url}")
        return response


class MetadataEnricherTests(unittest.TestCase):
    def test_semantic_scholar_enriches_missing_abstract_and_citations(self) -> None:
        doi = "10.1000/example"
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/batch?"
            "fields=abstract%2Ctldr%2CcitationCount%2CexternalIds"
        )
        client = FakeHttpClient(
            post_responses={
                url: [
                    {
                        "externalIds": {"DOI": doi},
                        "abstract": "Semantic Scholar abstract",
                        "citationCount": 42,
                        "tldr": {"text": "Short machine summary"},
                    }
                ]
            }
        )
        enricher = MetadataEnricher(
            semantic_scholar=SemanticScholarClient(http_client=client, api_key="key"),
            openalex=OpenAlexClient(http_client=FakeHttpClient()),
            sleep_seconds=0,
        )
        record = ArticleRecord(
            source_id="nature",
            journal="Nature",
            title="Political communication and AI",
            published_date="2026-03-25",
            doi=doi,
            abstract=None,
            provenance={},
        )
        enriched = enricher.enrich_records([record])[0]
        self.assertEqual(enriched.abstract, "Semantic Scholar abstract")
        self.assertEqual(enriched.provenance["abstract_source"], "semantic_scholar")
        self.assertEqual(enriched.provenance["citation_count"], 42)
        self.assertEqual(enriched.provenance["semantic_scholar_tldr"], "Short machine summary")

    def test_openalex_fallback_reconstructs_missing_abstract(self) -> None:
        doi = "10.1000/openalex"
        openalex_url = "https://api.openalex.org/works/doi:10.1000%2Fopenalex"
        client = FakeHttpClient(
            get_responses={
                openalex_url: {
                    "abstract_inverted_index": {
                        "Political": [0],
                        "behavior": [1],
                        "study": [2],
                    }
                }
            }
        )
        enricher = MetadataEnricher(
            semantic_scholar=SemanticScholarClient(http_client=FakeHttpClient(), api_key=None),
            openalex=OpenAlexClient(http_client=client),
            sleep_seconds=0,
        )
        record = ArticleRecord(
            source_id="science",
            journal="Science",
            title="Political behavior study",
            published_date="2026-03-25",
            doi=doi,
            abstract=None,
            provenance={},
        )
        enriched = enricher.enrich_records([record])[0]
        self.assertEqual(enriched.abstract, "Political behavior study")
        self.assertEqual(enriched.provenance["abstract_source"], "openalex")

    def test_enricher_preserves_crossref_abstract(self) -> None:
        enricher = MetadataEnricher(
            semantic_scholar=SemanticScholarClient(http_client=FakeHttpClient(), api_key=None),
            openalex=OpenAlexClient(http_client=FakeHttpClient()),
            sleep_seconds=0,
        )
        record = ArticleRecord(
            source_id="ajps",
            journal="American Journal of Political Science",
            title="Existing abstract article",
            published_date="2026-03-25",
            doi="10.1000/kept",
            abstract="Crossref abstract",
            provenance={"abstract_source": "crossref"},
        )
        enriched = enricher.enrich_records([record])[0]
        self.assertEqual(enriched.abstract, "Crossref abstract")
        self.assertEqual(enriched.provenance["abstract_source"], "crossref")


class EnrichmentResilienceTests(unittest.TestCase):
    def test_openalex_404_returns_none(self) -> None:
        http_client = Mock()
        http_client.get_json.side_effect = HTTPError(
            url="https://api.openalex.org/works/doi:10.1000%2Fmissing",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        client = OpenAlexClient(http_client=http_client)

        self.assertIsNone(client.abstract_by_doi("10.1000/missing"))

    def test_semantic_scholar_batch_lookup_ignores_400(self) -> None:
        http_client = Mock()
        http_client.post_json.side_effect = HTTPError(
            url="https://api.semanticscholar.org/graph/v1/paper/batch",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=None,
        )
        client = SemanticScholarClient(http_client=http_client, api_key="test-key")

        self.assertEqual(client.batch_lookup_by_doi(["10.1000/problematic"]), {})

    def test_enrich_records_continues_when_optional_apis_fail(self) -> None:
        semantic_http = Mock()
        semantic_http.post_json.side_effect = HTTPError(
            url="https://api.semanticscholar.org/graph/v1/paper/batch",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None,
        )
        semantic_http.get_json.side_effect = HTTPError(
            url="https://api.semanticscholar.org/graph/v1/paper/search",
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None,
        )
        openalex_http = Mock()
        openalex_http.get_json.side_effect = HTTPError(
            url="https://api.openalex.org/works/doi:10.1000%2Fpaper",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=None,
        )
        enricher = MetadataEnricher(
            semantic_scholar=SemanticScholarClient(http_client=semantic_http, api_key="test-key"),
            openalex=OpenAlexClient(http_client=openalex_http),
            sleep_seconds=0,
        )
        records = [
            ArticleRecord(
                source_id="nature",
                journal="Nature",
                title="A paper",
                published_date="2026-04-06",
                doi="10.1000/paper",
                canonical_url="https://doi.org/10.1000/paper",
            )
        ]

        enriched = enricher.enrich_records(records)

        self.assertEqual(len(enriched), 1)
        self.assertIsNone(enriched[0].abstract)
        self.assertEqual(enriched[0].provenance["abstract_source"], "unavailable")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
