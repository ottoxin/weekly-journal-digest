from __future__ import annotations

import hashlib
import html
import re
from datetime import date


_DOI_PREFIX_RE = re.compile(r"^(?:https?://)?(?:dx\.)?doi\.org/", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    normalized = html.unescape(value).strip()
    normalized = _DOI_PREFIX_RE.sub("", normalized)
    normalized = normalized.strip().strip("/")
    return normalized.lower() or None


def canonicalize_url(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip()


def clean_abstract(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = html.unescape(value)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned or None


def make_dedupe_key(
    doi: str | None,
    canonical_url: str | None,
    journal: str,
    title: str,
    published_date: str,
) -> str:
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return f"doi:{normalized_doi}"
    if canonical_url:
        return f"url:{canonical_url.strip().lower()}"
    fingerprint = " | ".join(
        [
            journal.strip().lower(),
            normalize_whitespace(title).lower(),
            published_date,
        ]
    )
    return f"fallback:{hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()}"


def normalize_whitespace(value: str) -> str:
    return _WS_RE.sub(" ", value.strip())


def choose_best_abstract(primary: str | None, fallback: str | None) -> str | None:
    return clean_abstract(primary) or clean_abstract(fallback)


def date_from_parts(parts: list[list[int]] | None) -> str | None:
    if not parts:
        return None
    values = parts[0]
    if not values:
        return None
    year = values[0]
    month = values[1] if len(values) > 1 else 1
    day = values[2] if len(values) > 2 else 1
    return date(year, month, day).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
