from __future__ import annotations

from .models import ArticleRecord, SourceConfig

DEFAULT_EXCLUDED_TITLE_PREFIXES = (
    "Correction",
    "Corrigendum",
    "Erratum",
    "Retraction",
    "Expression of Concern",
    "Editorial",
    "Publisher Correction",
    "Author Correction",
)


def is_excluded_title(title: str, extra_prefixes: list[str] | None = None) -> bool:
    prefixes = list(DEFAULT_EXCLUDED_TITLE_PREFIXES)
    if extra_prefixes:
        prefixes.extend(extra_prefixes)
    lowered = title.strip().lower()
    return any(lowered.startswith(prefix.lower()) for prefix in prefixes)


def matches_social_science(article: ArticleRecord, keywords: list[str]) -> bool:
    haystack = " ".join(
        [
            article.title,
            article.abstract or "",
            " ".join(article.subjects),
        ]
    ).lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def should_include_record(
    source: SourceConfig,
    article: ArticleRecord,
    social_science_keywords: list[str],
) -> tuple[bool, str]:
    if not article.published_date:
        return False, "missing-published-date"
    if source.allowed_article_types and article.article_type not in source.allowed_article_types:
        return False, f"article-type:{article.article_type}"
    if is_excluded_title(article.title, source.exclude_title_prefixes):
        return False, "excluded-title-prefix"
    if source.require_social_science_match and not matches_social_science(article, social_science_keywords):
        return False, "not-social-science-related"
    return True, "included"
