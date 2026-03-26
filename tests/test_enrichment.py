from __future__ import annotations

import unittest

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


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
