from __future__ import annotations

from datetime import date

from ..crossref import CrossrefClient
from ..models import ArticleRecord, SourceConfig
from .base import SourceAdapter


class CrossrefAdapter(SourceAdapter):
    def __init__(self, client: CrossrefClient):
        self.client = client

    def collect(self, source: SourceConfig, start_date: date, end_date: date) -> list[ArticleRecord]:
        return self.client.fetch_source_records(source, start_date, end_date)
