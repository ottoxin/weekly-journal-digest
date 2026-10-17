"""Check the reviewed artifact against its collection handoff, without network access."""
from __future__ import annotations

from html import unescape
import re

from .reviewed_digest import parse_reviewed_digest, _structure_full_digest


SECTION_KEYS = {
    "New This Week": "new_this_week",
    "Previous Week Catch-Up": "previous_week_catch_up",
    "Late Additions": "late_additions",
}


def normalized(value: str) -> str:
    return " ".join(unescape(value or "").split())


def validate_reviewed_digest(candidate: dict, markdown: str) -> list[str]:
    reviewed = parse_reviewed_digest(markdown)
    if reviewed is None:
        return ["Invalid structured digest."]
    errors: list[str] = []
    windows = candidate["windows"]
    expected_subject = f"Weekly journal digest for {windows['new_this_week_start']} to {windows['new_this_week_end']}"
    if reviewed.subject != expected_subject:
        errors.append(f"Subject must match the candidate window: {expected_subject}")
    candidates = {
        (section, normalized(item["journal"]), normalized(item["title"])): item
        for section, items in candidate["sections"].items()
        for item in items
    }
    seen: set[str] = set()
    kept: dict[tuple[str, str], object] = {}
    parsed_count = 0
    for section in _structure_full_digest(reviewed.full_curated_digest_markdown):
        section_key = SECTION_KEYS.get(section.name)
        if section_key is None:
            errors.append(f"Unknown section: {section.name}")
        for journal in section.journals:
            for article in journal.articles:
                parsed_count += 1
                key = (section_key, normalized(journal.name), normalized(article.title))
                item = candidates.get(key)
                if item is None:
                    errors.append(f"Article not in candidate section/journal: {article.title}")
                    continue
                identity = (item.get("doi") or item.get("link") or repr(key)).lower()
                if identity in seen:
                    errors.append(f"Duplicate article: {article.title}")
                seen.add(identity)
                kept[(normalized(journal.name), normalized(article.title))] = article
                fields = {
                    "published": item["published_date"], "doi": item.get("doi") or "",
                    "link": item.get("link") or "", "abstract": item.get("abstract") or "Abstract unavailable.",
                    "authors": "; ".join(item.get("authors") or []),
                    "affiliations": "; ".join(item.get("affiliations") or []),
                }
                for field, expected in fields.items():
                    if normalized(getattr(article, field)) != normalized(expected):
                        errors.append(f"Changed or missing {field}: {article.title}")
    declared_count = len(re.findall(r"^\s*- \*\*", reviewed.full_curated_digest_markdown, re.MULTILINE))
    if declared_count != parsed_count:
        errors.append("Some article entries could not be parsed; check title syntax and section/journal headings.")
    snapshot_counts = {
        "Total collected candidates": sum(len(items) for items in candidate["sections"].values()),
        "New This Week candidates": len(candidate["sections"]["new_this_week"]),
        "Previous Week Catch-Up candidates": len(candidate["sections"]["previous_week_catch_up"]),
        "Late Additions candidates": len(candidate["sections"]["late_additions"]),
    }
    for line in reviewed.collection_snapshot:
        label, _, value = line.partition(":")
        if label in snapshot_counts and value.strip() != str(snapshot_counts[label]):
            errors.append(f"Incorrect collection snapshot count: {label}")
    for highlight in reviewed.highlights:
        article = kept.get((normalized(highlight.journal), normalized(highlight.title)))
        if article is None:
            errors.append(f"Highlight not in curated digest: {highlight.title}")
        elif highlight.published != article.published or highlight.link != article.link:
            errors.append(f"Highlight date/link differs: {highlight.title}")
    return errors
