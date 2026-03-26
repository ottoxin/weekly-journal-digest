from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ArticleRecord:
    source_id: str
    journal: str
    title: str
    published_date: str
    article_type: str = "journal-article"
    doi: str | None = None
    canonical_url: str | None = None
    published_online: str | None = None
    published_print: str | None = None
    abstract: str | None = None
    relevance_status: str = "included"
    authors: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SourceConfig:
    id: str
    journal: str
    category: str
    adapter: str
    issns: list[str] = field(default_factory=list)
    title_query: str | None = None
    allowed_article_types: list[str] = field(default_factory=lambda: ["journal-article"])
    exclude_title_prefixes: list[str] = field(default_factory=list)
    require_social_science_match: bool = False


@dataclass(slots=True)
class AppConfig:
    timezone: str
    default_lookback_days: int
    state_dir: str
    social_science_keywords: list[str]
    sources: list[SourceConfig]


@dataclass(slots=True)
class WeeklyWindows:
    digest_date: str
    new_this_week_start: str
    new_this_week_end: str
    previous_week_start: str
    previous_week_end: str
    late_additions_before: str
    late_additions_first_seen_since: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
