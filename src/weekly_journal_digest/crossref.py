from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlencode

from .http_client import JsonHttpClient
from .models import ArticleRecord, SourceConfig
from .normalize import canonicalize_url, clean_abstract, date_from_parts, normalize_doi, normalize_whitespace


class CrossrefClient:
    api_url = "https://api.crossref.org/works"

    def __init__(self, http_client: JsonHttpClient | None = None, mailto: str | None = None):
        self.http_client = http_client or JsonHttpClient()
        self.mailto = mailto

    def fetch_source_records(
        self,
        source: SourceConfig,
        start_date: date,
        end_date: date,
    ) -> list[ArticleRecord]:
        deduped: dict[str, ArticleRecord] = {}
        issns = source.issns or [None]
        for issn in issns:
            for item in self._iter_works(source, issn, start_date, end_date):
                record = self._item_to_record(source, item)
                key = record.doi or f"{record.journal}:{record.title}:{record.published_date}"
                existing = deduped.get(key)
                if existing and existing.abstract:
                    continue
                deduped[key] = record
        return sorted(
            deduped.values(),
            key=lambda record: (record.published_date, record.journal, record.title),
            reverse=True,
        )

    def _iter_works(
        self,
        source: SourceConfig,
        issn: str | None,
        start_date: date,
        end_date: date,
    ):
        cursor = "*"
        rows = 100
        while True:
            filters = [
                f"from-pub-date:{start_date.isoformat()}",
                f"until-pub-date:{end_date.isoformat()}",
                "type:journal-article",
            ]
            if issn:
                filters.append(f"issn:{issn}")
            params = {
                "rows": str(rows),
                "cursor": cursor,
                "sort": "published",
                "order": "desc",
                "filter": ",".join(filters),
            }
            if self.mailto:
                params["mailto"] = self.mailto
            if not issn:
                params["query.container-title"] = source.title_query or source.journal
            url = f"{self.api_url}?{urlencode(params)}"
            payload = self.http_client.get_json(url)
            message = payload["message"]
            items = message.get("items", [])
            if not items:
                break
            for item in items:
                yield item
            next_cursor = message.get("next-cursor")
            if not next_cursor or next_cursor == cursor or len(items) < rows:
                break
            cursor = next_cursor

    def _item_to_record(self, source: SourceConfig, item: dict[str, Any]) -> ArticleRecord:
        title = normalize_whitespace((item.get("title") or ["Untitled article"])[0])
        published_online = date_from_parts(item.get("published-online", {}).get("date-parts"))
        published_print = date_from_parts(item.get("published-print", {}).get("date-parts"))
        issued = date_from_parts(item.get("issued", {}).get("date-parts"))
        created = (item.get("created") or {}).get("date-time", "")[:10] or None
        authors = []
        for author in item.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            name = " ".join(part for part in [given, family] if part)
            if name:
                authors.append(name)
        return ArticleRecord(
            source_id=source.id,
            journal=source.journal,
            title=title,
            published_date=published_online or published_print or issued or created or "1900-01-01",
            article_type=item.get("type", "journal-article"),
            doi=normalize_doi(item.get("DOI")),
            canonical_url=canonicalize_url(item.get("URL")),
            published_online=published_online,
            published_print=published_print,
            abstract=clean_abstract(item.get("abstract")),
            authors=authors,
            subjects=sorted(set(item.get("subject", []))),
            provenance={
                "source": "crossref",
                "crossref_issn": item.get("ISSN", []),
                "container_title": (item.get("container-title") or [source.journal])[0],
                "publisher": item.get("publisher"),
                "subtype": item.get("subtype"),
            },
        )
