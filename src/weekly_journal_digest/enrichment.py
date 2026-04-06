from __future__ import annotations

import time
from dataclasses import replace
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode

from .http_client import JsonHttpClient, TransientHttpError, is_transient_network_error
from .models import ArticleRecord
from .normalize import clean_abstract


BEST_EFFORT_HTTP_STATUS_CODES = {400, 404, 408, 409, 425, 429, 500, 502, 503, 504}


class SemanticScholarClient:
    base_url = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, http_client: JsonHttpClient | None = None, api_key: str | None = None):
        self.http_client = http_client or JsonHttpClient()
        self.api_key = api_key

    def is_enabled(self) -> bool:
        return bool(self.api_key)

    def batch_lookup_by_doi(self, dois: list[str]) -> dict[str, dict[str, Any]]:
        if not self.api_key or not dois:
            return {}
        payload = {"ids": [f"DOI:{doi}" for doi in dois]}
        url = (
            f"{self.base_url}/paper/batch?"
            + urlencode({"fields": "abstract,tldr,citationCount,externalIds"})
        )
        try:
            data = self.http_client.post_json(url, payload, headers={"x-api-key": self.api_key})
        except Exception as exc:
            if _should_ignore_enrichment_error(exc):
                return {}
            raise
        results: dict[str, dict[str, Any]] = {}
        for item in data:
            external_ids = (item or {}).get("externalIds") or {}
            doi = (external_ids.get("DOI") or "").lower()
            if doi:
                results[doi] = item
        return results

    def search_abstract_by_title(self, title: str) -> str | None:
        if not self.api_key or not title:
            return None
        url = (
            f"{self.base_url}/paper/search?"
            + urlencode({"query": title, "fields": "title,abstract", "limit": 3})
        )
        try:
            payload = self.http_client.get_json(url, headers={"x-api-key": self.api_key})
        except Exception as exc:
            if _should_ignore_enrichment_error(exc):
                return None
            raise
        target = title.strip().lower()
        for item in payload.get("data", []):
            candidate_title = (item.get("title") or "").strip().lower()
            if candidate_title == target:
                return clean_abstract(item.get("abstract"))
        return None


class OpenAlexClient:
    base_url = "https://api.openalex.org/works"

    def __init__(self, http_client: JsonHttpClient | None = None):
        self.http_client = http_client or JsonHttpClient()

    def abstract_by_doi(self, doi: str) -> str | None:
        if not doi:
            return None
        url = f"{self.base_url}/doi:{quote(doi, safe='')}"
        try:
            payload = self.http_client.get_json(url)
        except Exception as exc:
            if _should_ignore_enrichment_error(exc):
                return None
            raise
        inverted = payload.get("abstract_inverted_index") or {}
        if not inverted:
            return None
        positioned_words = [
            (position, word)
            for word, positions in inverted.items()
            for position in positions
        ]
        positioned_words.sort()
        text = " ".join(word for _, word in positioned_words)
        return clean_abstract(text)


class MetadataEnricher:
    def __init__(
        self,
        semantic_scholar: SemanticScholarClient | None = None,
        openalex: OpenAlexClient | None = None,
        sleep_seconds: float = 0.2,
    ):
        self.semantic_scholar = semantic_scholar or SemanticScholarClient()
        self.openalex = openalex or OpenAlexClient()
        self.sleep_seconds = sleep_seconds

    def enrich_records(self, records: list[ArticleRecord]) -> list[ArticleRecord]:
        by_doi = {record.doi: record for record in records if record.doi}
        if by_doi and self.semantic_scholar.is_enabled():
            enriched = self.semantic_scholar.batch_lookup_by_doi(sorted(by_doi))
            for doi, payload in enriched.items():
                record = by_doi.get(doi)
                if record is None:
                    continue
                self._apply_semantic_scholar_payload(record, payload)
            if enriched:
                time.sleep(self.sleep_seconds)

        for record in records:
            if record.abstract:
                record.provenance.setdefault("abstract_source", "crossref")
                continue
            if record.doi:
                openalex_abstract = self.openalex.abstract_by_doi(record.doi)
                if openalex_abstract:
                    record.abstract = openalex_abstract
                    record.provenance["abstract_source"] = "openalex"
                    time.sleep(self.sleep_seconds)
                    continue
            if not record.abstract and self.semantic_scholar.is_enabled():
                title_abstract = self.semantic_scholar.search_abstract_by_title(record.title)
                if title_abstract:
                    record.abstract = title_abstract
                    record.provenance["abstract_source"] = "semantic_scholar_title_search"
                    time.sleep(self.sleep_seconds)
                    continue
            record.provenance.setdefault("abstract_source", "unavailable")
        return records

    def _apply_semantic_scholar_payload(self, record: ArticleRecord, payload: dict[str, Any]) -> None:
        citation_count = payload.get("citationCount")
        if citation_count is not None:
            record.provenance["citation_count"] = citation_count
        semantic_abstract = clean_abstract(payload.get("abstract"))
        tldr = payload.get("tldr")
        if isinstance(tldr, dict):
            tldr_text = clean_abstract(tldr.get("text"))
        else:
            tldr_text = None
        if tldr_text:
            record.provenance["semantic_scholar_tldr"] = tldr_text
        if not record.abstract and semantic_abstract:
            record.abstract = semantic_abstract
            record.provenance["abstract_source"] = "semantic_scholar"


def build_metadata_enricher(
    semantic_scholar_api_key: str | None = None,
    http_client: JsonHttpClient | None = None,
) -> MetadataEnricher:
    return MetadataEnricher(
        semantic_scholar=SemanticScholarClient(http_client=http_client, api_key=semantic_scholar_api_key),
        openalex=OpenAlexClient(http_client=http_client),
    )


def _should_ignore_enrichment_error(exc: BaseException) -> bool:
    for current in _iter_exception_chain(exc):
        if isinstance(current, HTTPError) and current.code in BEST_EFFORT_HTTP_STATUS_CODES:
            return True
        if isinstance(current, (TransientHttpError, URLError)) and is_transient_network_error(current):
            return True
        if is_transient_network_error(current):
            return True
    return False


def _iter_exception_chain(exc: BaseException):
    pending = [exc]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        if current.__context__ is not None:
            pending.append(current.__context__)
