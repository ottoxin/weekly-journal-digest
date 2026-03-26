from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from ..models import ArticleRecord, SourceConfig


class SourceAdapter(ABC):
    @abstractmethod
    def collect(self, source: SourceConfig, start_date: date, end_date: date) -> list[ArticleRecord]:
        raise NotImplementedError
