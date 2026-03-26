from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from .models import AppConfig, ArticleRecord, WeeklyWindows
from .storage import StateStore


def compute_weekly_windows(digest_date: date) -> WeeklyWindows:
    new_start = digest_date - timedelta(days=7)
    new_end_exclusive = digest_date
    previous_start = digest_date - timedelta(days=14)
    previous_end_exclusive = digest_date - timedelta(days=7)
    first_seen_since = datetime.combine(new_start, time.min, tzinfo=timezone.utc)
    return WeeklyWindows(
        digest_date=digest_date.isoformat(),
        new_this_week_start=new_start.isoformat(),
        new_this_week_end=(new_end_exclusive - timedelta(days=1)).isoformat(),
        previous_week_start=previous_start.isoformat(),
        previous_week_end=(previous_end_exclusive - timedelta(days=1)).isoformat(),
        late_additions_before=previous_start.isoformat(),
        late_additions_first_seen_since=first_seen_since.isoformat(),
    )


def build_candidate_digest(
    store: StateStore,
    config: AppConfig,
    digest_date: date,
    output_path: str | Path,
    generated_at: datetime | None = None,
) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc)
    windows = compute_weekly_windows(digest_date)
    new_end_exclusive = digest_date.isoformat()
    previous_end_exclusive = (digest_date - timedelta(days=7)).isoformat()
    new_this_week = store.get_articles_between(windows.new_this_week_start, new_end_exclusive)
    previous_week = store.get_articles_between(windows.previous_week_start, previous_end_exclusive)
    late_additions = store.get_late_additions(
        windows.late_additions_before,
        windows.late_additions_first_seen_since,
        generated_at.isoformat(),
    )
    payload = {
        "digest_key": digest_date.isoformat(),
        "generated_at": generated_at.isoformat(),
        "timezone": config.timezone,
        "lookback_days": config.default_lookback_days,
        "tracked_journals": [source.journal for source in config.sources],
        "windows": asdict(windows),
        "sections": {
            "new_this_week": [_article_to_digest_item(article) for article in new_this_week],
            "previous_week_catch_up": [_article_to_digest_item(article) for article in previous_week],
            "late_additions": [_article_to_digest_item(article) for article in late_additions],
        },
    }
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return payload


def _article_to_digest_item(article: ArticleRecord) -> dict:
    return {
        "journal": article.journal,
        "title": article.title,
        "published_date": article.published_date,
        "link": article.canonical_url,
        "doi": article.doi,
        "abstract": article.abstract or "Abstract unavailable.",
        "article_type": article.article_type,
        "subjects": article.subjects,
        "first_seen_at": article.first_seen_at,
        "authors": article.authors,
        "affiliations": article.affiliations,
        "citation_count": article.provenance.get("citation_count"),
        "abstract_source": article.provenance.get("abstract_source"),
        "semantic_scholar_tldr": article.provenance.get("semantic_scholar_tldr"),
    }
