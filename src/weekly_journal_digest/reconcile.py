from __future__ import annotations

from dataclasses import replace

from .models import ArticleRecord
from .normalize import choose_best_abstract


def reconcile_with_crossref(primary: ArticleRecord, crossref: ArticleRecord) -> ArticleRecord:
    merged = replace(primary)
    merged.doi = merged.doi or crossref.doi
    merged.canonical_url = merged.canonical_url or crossref.canonical_url
    merged.published_online = merged.published_online or crossref.published_online
    merged.published_print = merged.published_print or crossref.published_print
    merged.published_date = merged.published_date or crossref.published_date
    merged.abstract = choose_best_abstract(primary.abstract, crossref.abstract)
    merged.authors = merged.authors or crossref.authors
    merged.subjects = sorted(set(merged.subjects) | set(crossref.subjects))
    merged.provenance = {
        **crossref.provenance,
        **primary.provenance,
        "reconciled_with": "crossref",
    }
    return merged
