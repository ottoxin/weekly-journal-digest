from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from html import escape as _html_escape, unescape
from io import BytesIO


def escape(value: str, quote: bool = False) -> str:
    """Escape after first unescaping, so pre-escaped source text isn't double-escaped."""
    return _html_escape(unescape(value), quote=quote)

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


BOT_NAME = "COMAP Journal Bot"
DELIVERY_PREFERENCES_TEXT = "Delivery preferences can be changed in the local recipient configuration."

PAGE_WIDTH, PAGE_HEIGHT = LETTER

PALETTE = {
    "ink": "#0b2545",
    "ink_soft": "#1f2937",
    "muted": "#52606d",
    "muted_soft": "#7b8794",
    "accent": "#1f6feb",
    "accent_dark": "#0a4faf",
    "accent_soft": "#e7efff",
    "highlight": "#b45309",
    "highlight_bg": "#fff7ed",
    "surface": "#ffffff",
    "surface_alt": "#f6f8fb",
    "surface_band": "#eef2f8",
    "border": "#e2e8f0",
    "border_soft": "#eef0f4",
    "section_band": "#0b2545",
    "subsection_band": "#1f6feb",
}

SECTION_COLOR_MAP = {
    "New This Week": ("#0b2545", "#e7efff"),
    "Previous Week Catch-Up": ("#134e4a", "#e6fffa"),
    "Late Additions": ("#7c2d12", "#fff7ed"),
}


@dataclass(slots=True)
class Highlight:
    title: str
    journal: str
    published: str
    why_it_matters: str
    link: str


@dataclass(slots=True)
class OutlineEntry:
    label: str
    section: str
    journal: str
    anchor: str


@dataclass(slots=True)
class FullDigestArticle:
    title: str
    published: str = ""
    authors: str = ""
    affiliations: str = ""
    doi: str = ""
    link: str = ""
    abstract: str = ""


@dataclass(slots=True)
class FullDigestJournal:
    name: str
    anchor: str
    articles: list[FullDigestArticle]


@dataclass(slots=True)
class FullDigestSection:
    name: str
    journals: list[FullDigestJournal]


@dataclass(slots=True)
class ReviewedDigest:
    subject: str
    summary: str
    collection_snapshot: list[str]
    highlights: list[Highlight]
    full_curated_digest_markdown: str


def parse_reviewed_digest(markdown_body: str) -> ReviewedDigest | None:
    subject, body = _extract_subject(markdown_body)
    if not subject:
        return None
    sections = _split_h2_sections(body)
    summary_section_name = "Summary" if "Summary" in sections else "Email Summary"
    required = {
        summary_section_name,
        "Highlights",
        "Full Curated Digest",
    }
    if not required.issubset(sections):
        return None
    summary = "\n".join(sections[summary_section_name]).strip()
    collection_snapshot = [
        line.strip()[2:].strip()
        for line in sections.get("Collection Snapshot", [])
        if line.strip().startswith("- ")
    ]
    highlights = _parse_highlights(sections["Highlights"])
    full_curated_digest_markdown = "\n".join(sections["Full Curated Digest"]).strip()
    if not summary or not highlights or not full_curated_digest_markdown:
        return None
    return ReviewedDigest(
        subject=subject,
        summary=summary,
        collection_snapshot=collection_snapshot,
        highlights=highlights,
        full_curated_digest_markdown=full_curated_digest_markdown,
    )


def render_summary_plain_text(
    reviewed: ReviewedDigest,
    recipient_name: str | None = None,
) -> str:
    lines = [
        f"Dear {_salutation_name(recipient_name)},",
        "",
        reviewed.summary.strip(),
        "",
        "Highlights",
    ]
    for highlight in reviewed.highlights:
        lines.append(f"- {highlight.title}")
        meta = " | ".join(part for part in [highlight.journal, highlight.published] if part)
        if meta:
            lines.append(f"  {meta}")
        if highlight.why_it_matters:
            lines.append(f"  Why it matters: {highlight.why_it_matters}")
        if highlight.link:
            lines.append(f"  Link: {highlight.link}")
        lines.append("")
    lines.append("The full curated digest is attached as a PDF. A browser-ready HTML version is also generated.")
    lines.extend(["", BOT_NAME, "", DELIVERY_PREFERENCES_TEXT])
    return "\n".join(lines).strip() + "\n"


def render_summary_html(
    reviewed: ReviewedDigest,
    recipient_name: str | None = None,
    *,
    include_full_digest: bool = False,
) -> str:
    summary_html = _render_summary_blocks_html(reviewed.summary)
    highlight_cards = []
    for highlight in reviewed.highlights:
        meta_parts = [part for part in [highlight.journal, highlight.published] if part]
        meta = " &middot; ".join(escape(part) for part in meta_parts)
        highlight_cards.append(
            "".join(
                [
                    "<div style=\"border:1px solid #dde4ed; border-left:4px solid #1f6feb;"
                    " border-radius:12px; padding:16px 18px; margin:0 0 14px 0; background:#ffffff;\">",
                    f"<div style=\"font-size:16px; font-weight:700; color:#0b2545; line-height:1.35; margin:0 0 6px 0;\">{escape(highlight.title)}</div>",
                    f"<div style=\"font-size:12px; color:#52606d; text-transform:uppercase; letter-spacing:0.04em; margin:0 0 10px 0;\">{meta}</div>"
                    if meta
                    else "",
                    f"<div style=\"font-size:14px; line-height:1.6; color:#1f2937; margin:0 0 12px 0;\"><strong style=\"color:#0b2545;\">Why it matters &middot;</strong> {escape(highlight.why_it_matters)}</div>"
                    if highlight.why_it_matters
                    else "",
                    f"<a href=\"{escape(highlight.link, quote=True)}\""
                    " style=\"display:inline-block; padding:8px 14px; background:#1f6feb; color:#ffffff;"
                    " text-decoration:none; border-radius:999px; font-size:13px; font-weight:600;\">Open article &rarr;</a>"
                    if highlight.link
                    else "",
                    "</div>",
                ]
            )
        )
    full_digest_html = _render_email_full_digest_html(reviewed) if include_full_digest else ""
    digest_callout = (
        "The full curated digest is included below. The attached PDF is also available for archive and printing."
        if include_full_digest
        else "The attached PDF includes the full curated digest, abstract-level details, and a journal table of contents."
    )
    return (
        "<html><body style=\"margin:0; padding:0; background:#eef2f8;"
        " font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;\">"
        "<div style=\"max-width:760px; margin:0 auto; padding:24px 16px;\">"
        "<div style=\"background:#ffffff; border-radius:18px; overflow:hidden;"
        " box-shadow:0 10px 30px rgba(15,23,42,0.08);\">"
        "<div style=\"background:#0b2545; padding:22px 28px; color:#ffffff;\">"
        f"<div style=\"font-size:11px; letter-spacing:0.16em; text-transform:uppercase; color:#9ab1d4; margin:0 0 6px 0;\">{escape(BOT_NAME)}</div>"
        f"<h1 style=\"margin:0; font-size:24px; line-height:1.25; color:#ffffff;\">{escape(reviewed.subject)}</h1>"
        "</div>"
        "<div style=\"padding:24px 28px 26px 28px;\">"
        f"<p style=\"margin:0 0 16px 0; font-size:15px; line-height:1.55; color:#1f2937;\">Dear {escape(_salutation_name(recipient_name))},</p>"
        "<h2 style=\"margin:0 0 14px 0; font-size:13px; letter-spacing:0.12em; text-transform:uppercase; color:#1f6feb;\">Summary</h2>"
        f"{summary_html}"
        "<h2 style=\"margin:26px 0 14px 0; font-size:13px; letter-spacing:0.12em; text-transform:uppercase; color:#1f6feb;\">Highlights</h2>"
        f"{''.join(highlight_cards)}"
        f"{full_digest_html}"
        "<div style=\"margin-top:18px; padding:14px 16px; border-radius:12px; background:#f6f8fb;"
        " color:#334e68; font-size:13px; line-height:1.55;\">"
        f"{escape(digest_callout)}"
        "</div>"
        "<div style=\"margin-top:20px; font-size:15px; line-height:1.4; font-weight:700; color:#0b2545;\">"
        f"{escape(BOT_NAME)}"
        "</div>"
        "<div style=\"margin-top:8px; font-size:12px; line-height:1.5; color:#52606d;\">"
        f"{escape(DELIVERY_PREFERENCES_TEXT)}"
        "</div>"
        "</div></div></div></body></html>"
    )


def render_curated_digest_pdf(reviewed: ReviewedDigest) -> bytes:
    buffer = BytesIO()
    subject_text = _to_pdf_text(reviewed.subject)
    doc = BaseDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.75 * inch,
        title=subject_text,
        author=BOT_NAME,
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="content",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    page_template = PageTemplate(
        id="default",
        frames=[frame],
        onPage=_build_page_chrome(subject_text),
    )
    doc.addPageTemplates([page_template])
    styles = _build_pdf_styles()
    structured = _structure_full_digest(reviewed.full_curated_digest_markdown)
    story: list = []
    story.extend(_pdf_cover_block(reviewed, styles))
    story.extend(_pdf_summary_block(reviewed, styles))
    story.extend(_pdf_highlights_block(reviewed, styles))
    if structured:
        story.extend(_pdf_toc_block(structured, styles))
    if reviewed.collection_snapshot:
        story.extend(_pdf_snapshot_block(reviewed.collection_snapshot, styles))
    story.extend(_pdf_full_digest_block(structured, styles))
    doc.build(story)
    return buffer.getvalue()


def render_full_digest_html(reviewed: ReviewedDigest) -> str:
    structured = _structure_full_digest(reviewed.full_curated_digest_markdown)
    summary_html = _render_summary_blocks_full_html(reviewed.summary)
    highlights_html = _render_highlights_full_html(reviewed.highlights)
    snapshot_html = _render_snapshot_full_html(reviewed.collection_snapshot)
    toc_html, body_html = _render_full_digest_sections_html(structured)
    css = _full_html_css()
    return (
        "<!doctype html>"
        "<html lang=\"en\">"
        "<head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{escape(reviewed.subject)}</title>"
        f"<style>{css}</style>"
        "</head>"
        "<body>"
        "<header class=\"page-header\">"
        "<div class=\"page-header__inner\">"
        f"<div class=\"page-header__eyebrow\">{escape(BOT_NAME)}</div>"
        f"<h1 class=\"page-header__title\">{escape(reviewed.subject)}</h1>"
        "<div class=\"page-header__meta\">A curated weekly digest of new articles in political communication and computational social science.</div>"
        "</div>"
        "</header>"
        "<div class=\"layout\">"
        "<aside class=\"toc\">"
        "<div class=\"toc__title\">In this digest</div>"
        "<nav class=\"toc__list\">"
        "<a class=\"toc__group-link\" href=\"#summary\">Summary</a>"
        "<a class=\"toc__group-link\" href=\"#highlights\">Highlights</a>"
        + (
            "<a class=\"toc__group-link\" href=\"#snapshot\">Collection Snapshot</a>"
            if reviewed.collection_snapshot
            else ""
        )
        + "<a class=\"toc__group-link\" href=\"#full-digest\">Full Curated Digest</a>"
        + toc_html
        + "</nav>"
        "</aside>"
        "<main class=\"main\">"
        "<section id=\"summary\" class=\"section section--summary\">"
        "<h2 class=\"section__title\">Summary</h2>"
        f"<div class=\"summary-body\">{summary_html}</div>"
        "</section>"
        "<section id=\"highlights\" class=\"section section--highlights\">"
        "<h2 class=\"section__title\">Highlights</h2>"
        f"<div class=\"highlight-grid\">{highlights_html}</div>"
        "</section>"
        + (
            "<section id=\"snapshot\" class=\"section section--snapshot\">"
            "<h2 class=\"section__title\">Collection Snapshot</h2>"
            f"<div class=\"snapshot-grid\">{snapshot_html}</div>"
            "</section>"
            if reviewed.collection_snapshot
            else ""
        )
        + "<section id=\"full-digest\" class=\"section section--digest\">"
        "<h2 class=\"section__title\">Full Curated Digest</h2>"
        f"{body_html}"
        "</section>"
        "</main>"
        "</div>"
        "<footer class=\"page-footer\">"
        f"<div>{escape(BOT_NAME)} &middot; {escape(reviewed.subject)}</div>"
        "</footer>"
        "</body></html>"
    )


def _salutation_name(recipient_name: str | None) -> str:
    cleaned = " ".join((recipient_name or "").split())
    return cleaned or "Reader"


def _render_email_full_digest_html(reviewed: ReviewedDigest) -> str:
    blocks = []
    if reviewed.collection_snapshot:
        snapshot_items = "".join(
            f"<li style=\"margin:0 0 6px 0;\">{escape(item)}</li>"
            for item in reviewed.collection_snapshot
        )
        blocks.append(
            "<h2 style=\"margin:28px 0 12px 0; font-size:13px; letter-spacing:0.12em; "
            "text-transform:uppercase; color:#1f6feb;\">Collection Snapshot</h2>"
            "<ul style=\"margin:0 0 18px 18px; padding:0; color:#1f2937; font-size:14px; "
            f"line-height:1.55;\">{snapshot_items}</ul>"
        )
    blocks.append(
        "<h2 style=\"margin:28px 0 12px 0; font-size:13px; letter-spacing:0.12em; "
        "text-transform:uppercase; color:#1f6feb;\">Full Curated Digest</h2>"
    )
    sections = _structure_full_digest(reviewed.full_curated_digest_markdown)
    if not sections:
        blocks.append(
            "<div style=\"white-space:pre-wrap; color:#1f2937; font-size:14px; line-height:1.6;\">"
            f"{escape(reviewed.full_curated_digest_markdown)}"
            "</div>"
        )
        return "".join(blocks)
    for section in sections:
        blocks.append(
            "<div style=\"margin:18px 0 10px 0; padding:10px 12px; border-radius:10px; "
            "background:#e7efff; color:#0b2545; font-size:15px; font-weight:700;\">"
            f"{escape(section.name)}</div>"
        )
        for journal in section.journals:
            blocks.append(
                "<h3 style=\"margin:16px 0 10px 0; font-size:16px; line-height:1.35; color:#0b2545;\">"
                f"{escape(journal.name)}</h3>"
            )
            for article in journal.articles:
                meta_parts = [
                    part
                    for part in [
                        article.published,
                        f"DOI {article.doi}" if article.doi else "",
                    ]
                    if part
                ]
                meta = " | ".join(meta_parts)
                blocks.append(
                    "<div style=\"margin:0 0 14px 0; padding:14px 16px; border:1px solid #dde4ed; "
                    "border-radius:10px; background:#ffffff;\">"
                    f"<div style=\"font-size:15px; font-weight:700; line-height:1.35; color:#0b2545;\">{escape(article.title)}</div>"
                    + (
                        f"<div style=\"margin-top:5px; font-size:12px; line-height:1.45; color:#52606d;\">{escape(meta)}</div>"
                        if meta
                        else ""
                    )
                    + (
                        f"<div style=\"margin-top:8px; font-size:13px; line-height:1.5; color:#334155;\"><strong>Authors:</strong> {escape(article.authors)}</div>"
                        if article.authors
                        else ""
                    )
                    + (
                        f"<div style=\"margin-top:8px; font-size:13px; line-height:1.5; color:#334155;\"><strong>Affiliations:</strong> {escape(article.affiliations)}</div>"
                        if article.affiliations
                        else ""
                    )
                    + (
                        f"<div style=\"margin-top:8px; font-size:14px; line-height:1.6; color:#1f2937;\">{escape(article.abstract)}</div>"
                        if article.abstract
                        else ""
                    )
                    + (
                        f"<a href=\"{escape(article.link, quote=True)}\" style=\"display:inline-block; margin-top:10px; color:#1f6feb; font-size:13px; font-weight:700; text-decoration:none;\">Open article</a>"
                        if article.link
                        else ""
                    )
                    + "</div>"
                )
    return "".join(blocks)


def _extract_subject(markdown_body: str) -> tuple[str | None, str]:
    lines = markdown_body.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = "\n".join(lines[1:]).lstrip()
        return subject, body
    return None, markdown_body


def _split_h2_sections(body: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_name: str | None = None
    current_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("## "):
            if current_name is not None:
                sections[current_name] = _trim_blank_lines(current_lines)
            current_name = line[3:].strip()
            current_lines = []
            continue
        if current_name is not None:
            current_lines.append(line)
    if current_name is not None:
        sections[current_name] = _trim_blank_lines(current_lines)
    return sections


def _trim_blank_lines(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _parse_highlights(lines: list[str]) -> list[Highlight]:
    highlights: list[Highlight] = []
    current: Highlight | None = None
    title_pattern = re.compile(r"^- \*\*(.+?)\*\*$")
    for line in lines + [""]:
        stripped = line.strip()
        title_match = title_pattern.match(stripped)
        if title_match:
            if current is not None:
                highlights.append(current)
            current = Highlight(
                title=title_match.group(1).strip(),
                journal="",
                published="",
                why_it_matters="",
                link="",
            )
            continue
        if current is None or not stripped:
            continue
        if stripped.startswith("Journal: "):
            current.journal = stripped.removeprefix("Journal: ").strip()
        elif stripped.startswith("Published: "):
            current.published = stripped.removeprefix("Published: ").strip()
        elif stripped.startswith("Why it matters: "):
            current.why_it_matters = stripped.removeprefix("Why it matters: ").strip()
        elif stripped.startswith("Link: "):
            current.link = stripped.removeprefix("Link: ").strip()
        elif current.why_it_matters:
            current.why_it_matters = f"{current.why_it_matters} {stripped}".strip()
    if current is not None:
        highlights.append(current)
    return [highlight for highlight in highlights if highlight.title]


def _summary_blocks(text: str) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    paragraph_lines: list[str] = []
    bullet_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            blocks.append(("paragraph", [" ".join(paragraph_lines)]))
            paragraph_lines.clear()

    def flush_bullets() -> None:
        if bullet_lines:
            blocks.append(("bullets", bullet_lines.copy()))
            bullet_lines.clear()

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            flush_paragraph()
            flush_bullets()
            continue
        if stripped.startswith("- "):
            flush_paragraph()
            bullet_lines.append(stripped[2:].strip())
            continue
        flush_bullets()
        paragraph_lines.append(stripped)
    flush_paragraph()
    flush_bullets()
    return blocks


def _render_summary_blocks_html(text: str) -> str:
    parts: list[str] = []
    for block_type, items in _summary_blocks(text):
        if block_type == "paragraph":
            parts.append(
                f"<p style=\"margin:0 0 12px 0; line-height:1.65; color:#1f2937; font-size:15px;\">{escape(items[0])}</p>"
            )
            continue
        bullet_items = "".join(
            f"<li style=\"margin:0 0 8px 0;\">{escape(item)}</li>" for item in items
        )
        parts.append(
            "<ul style=\"margin:0 0 18px 18px; padding:0; color:#243b53; line-height:1.6; font-size:15px;\">"
            f"{bullet_items}</ul>"
        )
    return "".join(parts)


def _render_summary_blocks_full_html(text: str) -> str:
    parts: list[str] = []
    for block_type, items in _summary_blocks(text):
        if block_type == "paragraph":
            parts.append(f"<p>{escape(items[0])}</p>")
            continue
        bullet_items = "".join(f"<li>{escape(item)}</li>" for item in items)
        parts.append(f"<ul>{bullet_items}</ul>")
    return "".join(parts)


def _render_highlights_full_html(highlights: list[Highlight]) -> str:
    cards = []
    for highlight in highlights:
        meta_parts = [escape(part) for part in [highlight.journal, highlight.published] if part]
        meta = " &middot; ".join(meta_parts)
        why_html = (
            f"<p class=\"highlight-card__why\"><span class=\"highlight-card__label\">Why it matters</span> {escape(highlight.why_it_matters)}</p>"
            if highlight.why_it_matters
            else ""
        )
        link_html = (
            f"<a class=\"highlight-card__cta\" href=\"{escape(highlight.link, quote=True)}\">Open article &rarr;</a>"
            if highlight.link
            else ""
        )
        meta_html = f"<div class=\"highlight-card__meta\">{meta}</div>" if meta else ""
        cards.append(
            "<article class=\"highlight-card\">"
            f"<h3 class=\"highlight-card__title\">{escape(highlight.title)}</h3>"
            f"{meta_html}{why_html}{link_html}"
            "</article>"
        )
    return "".join(cards)


def _render_snapshot_full_html(items: list[str]) -> str:
    cells = []
    for item in items:
        label, _, value = item.partition(":")
        if value:
            cells.append(
                "<div class=\"snapshot-card\">"
                f"<div class=\"snapshot-card__label\">{escape(label.strip())}</div>"
                f"<div class=\"snapshot-card__value\">{escape(value.strip())}</div>"
                "</div>"
            )
        else:
            cells.append(
                "<div class=\"snapshot-card snapshot-card--note\">"
                f"<div class=\"snapshot-card__value\">{escape(item.strip())}</div>"
                "</div>"
            )
    return "".join(cells)


def _render_full_digest_sections_html(
    structured: list[FullDigestSection],
) -> tuple[str, str]:
    toc_parts: list[str] = []
    body_parts: list[str] = []
    for section_index, section in enumerate(structured):
        section_anchor = f"section-{section_index + 1}"
        section_id = escape(section_anchor)
        toc_parts.append(
            "<div class=\"toc__group\">"
            f"<a class=\"toc__group-link toc__group-link--nested\" href=\"#{section_id}\">{escape(section.name)}</a>"
        )
        body_parts.append(
            f"<div id=\"{section_id}\" class=\"digest-section\">"
            f"<h3 class=\"digest-section__title\">{escape(section.name)}</h3>"
        )
        for journal in section.journals:
            journal_anchor = escape(journal.anchor)
            toc_parts.append(
                f"<a class=\"toc__journal-link\" href=\"#{journal_anchor}\">{escape(journal.name)}</a>"
            )
            body_parts.append(
                f"<div id=\"{journal_anchor}\" class=\"digest-journal\">"
                f"<h4 class=\"digest-journal__title\">{escape(journal.name)}</h4>"
                "<div class=\"digest-articles\">"
            )
            for article in journal.articles:
                body_parts.append(_render_full_html_article(article, section.name))
            body_parts.append("</div></div>")
        body_parts.append("</div>")
        toc_parts.append("</div>")
    return "".join(toc_parts), "".join(body_parts)


def _render_full_html_article(article: FullDigestArticle, section_name: str) -> str:
    meta_chips: list[str] = []
    if article.published:
        meta_chips.append(
            f"<span class=\"chip chip--date\">{escape(article.published)}</span>"
        )
    if section_name:
        meta_chips.append(
            f"<span class=\"chip chip--section\">{escape(section_name)}</span>"
        )
    if article.doi:
        meta_chips.append(
            f"<span class=\"chip chip--doi\">DOI {escape(article.doi)}</span>"
        )
    authors_html = (
        f"<p class=\"article__authors\">{escape(article.authors)}</p>"
        if article.authors
        else ""
    )
    affiliations_html = (
        f"<p class=\"article__affiliations\">{escape(article.affiliations)}</p>"
        if article.affiliations
        else ""
    )
    abstract_html = (
        f"<p class=\"article__abstract\">{escape(article.abstract)}</p>"
        if article.abstract
        else ""
    )
    link_html = (
        f"<a class=\"article__cta\" href=\"{escape(article.link, quote=True)}\">Read article &rarr;</a>"
        if article.link
        else ""
    )
    chips_html = (
        f"<div class=\"article__chips\">{''.join(meta_chips)}</div>" if meta_chips else ""
    )
    return (
        "<article class=\"article\">"
        f"<h5 class=\"article__title\">{escape(article.title)}</h5>"
        f"{chips_html}{authors_html}{affiliations_html}{abstract_html}{link_html}"
        "</article>"
    )


def _full_html_css() -> str:
    return (
        ":root {"
        "--ink:#0b2545; --ink-soft:#1f2937; --muted:#52606d; --muted-soft:#7b8794;"
        "--accent:#1f6feb; --accent-dark:#0a4faf; --accent-soft:#e7efff;"
        "--highlight:#b45309; --highlight-bg:#fff7ed; --surface:#ffffff;"
        "--surface-alt:#f6f8fb; --surface-band:#eef2f8; --border:#e2e8f0;"
        "--border-soft:#eef0f4;"
        "}"
        "* { box-sizing: border-box; }"
        "html, body { margin:0; padding:0; background:var(--surface-band);"
        " color:var(--ink-soft);"
        " font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
        " font-size:16px; line-height:1.6; }"
        "a { color:var(--accent); text-decoration:none; }"
        "a:hover { text-decoration:underline; }"
        ".page-header { background:linear-gradient(135deg,#0b2545 0%,#13315c 100%); color:#fff;"
        " padding:42px 24px 36px; }"
        ".page-header__inner { max-width:1080px; margin:0 auto; }"
        ".page-header__eyebrow { font-size:12px; letter-spacing:0.18em; text-transform:uppercase;"
        " color:#9ab1d4; margin-bottom:8px; font-weight:600; }"
        ".page-header__title { font-size:32px; line-height:1.2; margin:0 0 10px 0; color:#fff;"
        " font-weight:700; letter-spacing:-0.01em; }"
        ".page-header__meta { color:#c5d4ec; font-size:14px; max-width:640px; margin:0; }"
        ".layout { display:grid; grid-template-columns:260px minmax(0,1fr); gap:32px;"
        " max-width:1080px; margin:-12px auto 40px; padding:0 24px; }"
        ".toc { background:var(--surface); border:1px solid var(--border); border-radius:16px;"
        " padding:18px; box-shadow:0 6px 18px rgba(15,23,42,0.04); position:sticky; top:16px;"
        " align-self:start; max-height:calc(100vh - 32px); overflow:auto; font-size:14px; }"
        ".toc__title { font-size:11px; letter-spacing:0.16em; text-transform:uppercase;"
        " color:var(--muted); margin-bottom:12px; font-weight:700; }"
        ".toc__list { display:flex; flex-direction:column; gap:2px; }"
        ".toc__group { display:flex; flex-direction:column; gap:2px; margin-top:6px;"
        " padding-top:6px; border-top:1px solid var(--border-soft); }"
        ".toc__group:first-of-type { margin-top:10px; }"
        ".toc__group-link { font-weight:600; color:var(--ink); padding:6px 8px;"
        " border-radius:8px; }"
        ".toc__group-link--nested { color:var(--ink); }"
        ".toc__group-link:hover { background:var(--accent-soft); text-decoration:none; }"
        ".toc__journal-link { color:var(--muted); padding:5px 8px 5px 20px; border-radius:8px;"
        " font-size:13px; }"
        ".toc__journal-link:hover { background:var(--accent-soft); color:var(--accent-dark);"
        " text-decoration:none; }"
        ".main { display:flex; flex-direction:column; gap:24px; min-width:0; }"
        ".section { background:var(--surface); border-radius:18px; padding:24px 26px;"
        " border:1px solid var(--border); box-shadow:0 6px 18px rgba(15,23,42,0.04); }"
        ".section__title { margin:0 0 18px 0; font-size:13px; letter-spacing:0.14em;"
        " text-transform:uppercase; color:var(--accent); font-weight:700; }"
        ".summary-body p { margin:0 0 12px 0; font-size:16px; line-height:1.7;"
        " color:var(--ink-soft); }"
        ".summary-body ul { margin:0 0 14px 22px; padding:0; color:var(--ink-soft);"
        " line-height:1.65; }"
        ".summary-body ul li { margin-bottom:8px; }"
        ".highlight-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr));"
        " gap:16px; }"
        ".highlight-card { background:var(--surface); border:1px solid var(--border);"
        " border-left:4px solid var(--accent); border-radius:14px; padding:18px 18px 16px;"
        " display:flex; flex-direction:column; gap:8px; }"
        ".highlight-card__title { margin:0; font-size:16px; line-height:1.35; color:var(--ink);"
        " font-weight:700; }"
        ".highlight-card__meta { font-size:11px; letter-spacing:0.08em; text-transform:uppercase;"
        " color:var(--muted); }"
        ".highlight-card__why { margin:0; font-size:14px; line-height:1.55; color:var(--ink-soft); }"
        ".highlight-card__label { color:var(--accent-dark); font-weight:700; margin-right:4px; }"
        ".highlight-card__cta { display:inline-block; background:var(--accent); color:#fff;"
        " padding:8px 14px; border-radius:999px; font-size:13px; font-weight:600;"
        " align-self:flex-start; margin-top:auto; }"
        ".highlight-card__cta:hover { background:var(--accent-dark); text-decoration:none; }"
        ".snapshot-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr));"
        " gap:14px; }"
        ".snapshot-card { background:var(--surface-alt); border:1px solid var(--border-soft);"
        " border-radius:12px; padding:14px 16px; }"
        ".snapshot-card__label { font-size:11px; letter-spacing:0.1em; text-transform:uppercase;"
        " color:var(--muted); margin-bottom:6px; font-weight:600; }"
        ".snapshot-card__value { font-size:18px; font-weight:700; color:var(--ink); }"
        ".snapshot-card--note { grid-column:1/-1; background:transparent; border:none; padding:6px 0; }"
        ".snapshot-card--note .snapshot-card__value { font-size:13px; font-weight:400;"
        " color:var(--muted); }"
        ".digest-section { margin-top:8px; }"
        ".digest-section:first-of-type { margin-top:0; }"
        ".digest-section__title { font-size:20px; margin:18px 0 12px; color:var(--ink);"
        " padding-bottom:8px; border-bottom:2px solid var(--accent); }"
        ".digest-journal { margin-top:18px; }"
        ".digest-journal__title { font-size:14px; letter-spacing:0.06em; text-transform:uppercase;"
        " color:var(--accent-dark); margin:0 0 12px; padding:8px 14px; background:var(--accent-soft);"
        " border-radius:10px; display:inline-block; }"
        ".digest-articles { display:flex; flex-direction:column; gap:14px; }"
        ".article { background:var(--surface); border:1px solid var(--border-soft);"
        " border-left:3px solid var(--accent); border-radius:12px; padding:16px 18px;"
        " display:flex; flex-direction:column; gap:8px; }"
        ".article__title { margin:0; font-size:16px; line-height:1.35; color:var(--ink);"
        " font-weight:700; }"
        ".article__chips { display:flex; flex-wrap:wrap; gap:6px; }"
        ".chip { font-size:11px; letter-spacing:0.04em; padding:3px 9px; border-radius:999px;"
        " background:var(--surface-band); color:var(--muted); font-weight:600; }"
        ".chip--date { background:var(--accent-soft); color:var(--accent-dark); }"
        ".chip--section { background:#fef3c7; color:#92400e; }"
        ".chip--doi { background:#ecfdf5; color:#047857; font-family:'SFMono-Regular',Menlo,monospace;"
        " font-size:10px; }"
        ".article__authors { margin:0; font-size:13px; color:var(--muted); font-style:italic; }"
        ".article__affiliations { margin:0; font-size:12px; color:var(--muted-soft); }"
        ".article__abstract { margin:6px 0 0; font-size:14px; line-height:1.65;"
        " color:var(--ink-soft); }"
        ".article__cta { font-size:13px; font-weight:600; color:var(--accent); align-self:flex-start;"
        " margin-top:4px; }"
        ".page-footer { max-width:1080px; margin:0 auto; padding:20px 24px 36px; color:var(--muted);"
        " font-size:13px; text-align:center; }"
        "@media (max-width: 900px) {"
        " .layout { grid-template-columns:1fr; }"
        " .toc { position:static; max-height:none; }"
        " .page-header__title { font-size:26px; }"
        "}"
        "@media print {"
        " body { background:#fff; }"
        " .toc, .page-footer { display:none; }"
        " .layout { grid-template-columns:1fr; padding:0; margin:0; }"
        " .section { box-shadow:none; border:none; padding:8px 0; }"
        "}"
    )


def _structure_full_digest(markdown: str) -> list[FullDigestSection]:
    sections: list[FullDigestSection] = []
    current_section: FullDigestSection | None = None
    current_journal: FullDigestJournal | None = None
    current_article: FullDigestArticle | None = None
    seen: dict[tuple[str, str], int] = {}

    def flush_article() -> None:
        nonlocal current_article
        if current_article is None:
            return
        if current_journal is None:
            current_article = None
            return
        current_journal.articles.append(current_article)
        current_article = None

    def flush_journal() -> None:
        nonlocal current_journal
        flush_article()
        if current_journal and current_section:
            current_section.journals.append(current_journal)
        current_journal = None

    def flush_section() -> None:
        nonlocal current_section
        flush_journal()
        if current_section:
            sections.append(current_section)
        current_section = None

    body_line_target = None
    for raw_line in markdown.splitlines() + [""]:
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("### "):
            flush_section()
            current_section = FullDigestSection(name=stripped[4:].strip(), journals=[])
            continue
        if stripped.startswith("#### "):
            flush_journal()
            journal_name = stripped[5:].strip()
            section_name = current_section.name if current_section else ""
            key = (section_name, journal_name)
            seen[key] = seen.get(key, 0) + 1
            anchor = _outline_anchor(section_name, journal_name, seen[key])
            current_journal = FullDigestJournal(
                name=journal_name, anchor=anchor, articles=[]
            )
            continue
        title_match = re.match(r"^- \*\*(.+?)\*\*$", stripped)
        if title_match:
            flush_article()
            current_article = FullDigestArticle(title=title_match.group(1).strip())
            body_line_target = None
            continue
        if current_article is None:
            continue
        if not stripped:
            body_line_target = None
            continue
        attr_match = re.match(r"^(Published|Authors|Affiliations|DOI|Link|Abstract):\s*(.*)$", stripped)
        if attr_match:
            field = attr_match.group(1).lower()
            value = attr_match.group(2).strip()
            setattr(current_article, field, value)
            body_line_target = field if field in {"abstract", "authors", "affiliations"} else None
            continue
        if body_line_target == "abstract" and current_article.abstract:
            current_article.abstract = f"{current_article.abstract} {stripped}".strip()
        elif body_line_target == "authors" and current_article.authors:
            current_article.authors = f"{current_article.authors} {stripped}".strip()
        elif body_line_target == "affiliations" and current_article.affiliations:
            current_article.affiliations = (
                f"{current_article.affiliations} {stripped}".strip()
            )

    flush_section()
    return [section for section in sections if section.journals]


def _build_pdf_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    base = ParagraphStyle(
        "DigestBaseBody",
        parent=sample["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=13.5,
        textColor=colors.HexColor(PALETTE["ink_soft"]),
        spaceAfter=0,
    )
    return {
        "eyebrow": ParagraphStyle(
            "DigestEyebrow",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor(PALETTE["accent"]),
            spaceAfter=4,
        ),
        "title": ParagraphStyle(
            "DigestTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor(PALETTE["ink"]),
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "DigestSubtitle",
            parent=sample["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=8,
        ),
        "section_band": ParagraphStyle(
            "DigestSectionBand",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor(PALETTE["accent"]),
            spaceAfter=0,
        ),
        "section_band_label": ParagraphStyle(
            "DigestSectionBandLabel",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "digest_section_heading": ParagraphStyle(
            "DigestDigestSectionHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "journal_heading": ParagraphStyle(
            "DigestJournalHeading",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor(PALETTE["accent_dark"]),
            spaceAfter=0,
        ),
        "highlight_title": ParagraphStyle(
            "DigestHighlightTitle",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor(PALETTE["ink"]),
            spaceAfter=2,
        ),
        "highlight_meta": ParagraphStyle(
            "DigestHighlightMeta",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=4,
        ),
        "highlight_body": ParagraphStyle(
            "DigestHighlightBody",
            parent=base,
            fontSize=10,
            leading=13.5,
            spaceAfter=4,
        ),
        "highlight_link": ParagraphStyle(
            "DigestHighlightLink",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor(PALETTE["accent"]),
            spaceAfter=0,
        ),
        "body": ParagraphStyle(
            "DigestBody",
            parent=base,
            fontSize=10,
            leading=14,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "DigestBullet",
            parent=base,
            fontSize=10,
            leading=14,
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=4,
        ),
        "toc_section": ParagraphStyle(
            "DigestTocSection",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor(PALETTE["ink"]),
            spaceBefore=4,
            spaceAfter=2,
        ),
        "toc_entry": ParagraphStyle(
            "DigestTocEntry",
            parent=base,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor(PALETTE["accent_dark"]),
            leftIndent=14,
            spaceAfter=2,
        ),
        "article_title": ParagraphStyle(
            "DigestArticleTitle",
            parent=sample["Heading4"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor(PALETTE["ink"]),
            spaceAfter=2,
        ),
        "article_meta": ParagraphStyle(
            "DigestArticleMeta",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=2,
        ),
        "article_authors": ParagraphStyle(
            "DigestArticleAuthors",
            parent=base,
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=2,
        ),
        "article_affiliations": ParagraphStyle(
            "DigestArticleAffiliations",
            parent=base,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor(PALETTE["muted_soft"]),
            spaceAfter=4,
        ),
        "article_abstract": ParagraphStyle(
            "DigestArticleAbstract",
            parent=base,
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor(PALETTE["ink_soft"]),
            spaceAfter=4,
        ),
        "article_link": ParagraphStyle(
            "DigestArticleLink",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(PALETTE["accent"]),
            spaceAfter=0,
        ),
        "snapshot_label": ParagraphStyle(
            "DigestSnapshotLabel",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=2,
        ),
        "snapshot_value": ParagraphStyle(
            "DigestSnapshotValue",
            parent=base,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            textColor=colors.HexColor(PALETTE["ink"]),
            spaceAfter=0,
        ),
        "snapshot_note": ParagraphStyle(
            "DigestSnapshotNote",
            parent=base,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=0,
        ),
        "footer_note": ParagraphStyle(
            "DigestFooterNote",
            parent=base,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor(PALETTE["muted"]),
            spaceAfter=0,
        ),
    }


def _build_page_chrome(subject_text: str):
    def draw(canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            canvas.setFillColor(colors.HexColor(PALETTE["ink"]))
            canvas.rect(0, PAGE_HEIGHT - 0.4 * inch, PAGE_WIDTH, 0.4 * inch, fill=1, stroke=0)
            canvas.setFillColor(colors.white)
            canvas.setFont("Helvetica-Bold", 9)
            canvas.drawString(0.6 * inch, PAGE_HEIGHT - 0.255 * inch, BOT_NAME.upper())
            canvas.setFont("Helvetica", 9)
            canvas.setFillColor(colors.HexColor("#c5d4ec"))
            canvas.drawRightString(
                PAGE_WIDTH - 0.6 * inch,
                PAGE_HEIGHT - 0.255 * inch,
                subject_text,
            )
        else:
            canvas.setFillColor(colors.HexColor(PALETTE["ink"]))
            canvas.setFont("Helvetica-Bold", 8.5)
            canvas.drawString(0.6 * inch, PAGE_HEIGHT - 0.45 * inch, BOT_NAME)
            canvas.setFillColor(colors.HexColor(PALETTE["muted"]))
            canvas.setFont("Helvetica", 8.5)
            canvas.drawRightString(
                PAGE_WIDTH - 0.6 * inch, PAGE_HEIGHT - 0.45 * inch, subject_text
            )
            canvas.setStrokeColor(colors.HexColor(PALETTE["border"]))
            canvas.setLineWidth(0.5)
            canvas.line(
                0.6 * inch,
                PAGE_HEIGHT - 0.6 * inch,
                PAGE_WIDTH - 0.6 * inch,
                PAGE_HEIGHT - 0.6 * inch,
            )
        canvas.setFillColor(colors.HexColor(PALETTE["muted"]))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.6 * inch, 0.45 * inch, subject_text)
        canvas.drawRightString(
            PAGE_WIDTH - 0.6 * inch, 0.45 * inch, f"Page {doc.page}"
        )
        canvas.restoreState()

    return draw


def _pdf_cover_block(reviewed: ReviewedDigest, styles: dict[str, ParagraphStyle]) -> list:
    story: list = []
    story.append(Paragraph("WEEKLY JOURNAL DIGEST", styles["eyebrow"]))
    story.append(Paragraph(escape(_to_pdf_text(reviewed.subject)), styles["title"]))
    story.append(
        Paragraph(
            "Curated articles in political communication and computational social science.",
            styles["subtitle"],
        )
    )
    story.append(_accent_rule())
    story.append(Spacer(1, 0.16 * inch))
    return story


def _pdf_summary_block(reviewed: ReviewedDigest, styles: dict[str, ParagraphStyle]) -> list:
    story: list = [_section_band("Summary", styles)]
    for block_type, items in _summary_blocks(reviewed.summary):
        if block_type == "paragraph":
            story.append(
                Paragraph(escape(_to_pdf_text(items[0])), styles["body"])
            )
            continue
        for item in items:
            story.append(
                Paragraph(
                    f"&bull;&nbsp;&nbsp;{escape(_to_pdf_text(item))}",
                    styles["bullet"],
                )
            )
    story.append(Spacer(1, 0.16 * inch))
    return story


def _pdf_highlights_block(reviewed: ReviewedDigest, styles: dict[str, ParagraphStyle]) -> list:
    story: list = [_section_band("Highlights", styles)]
    for highlight in reviewed.highlights:
        inner: list = [
            Paragraph(escape(_to_pdf_text(highlight.title)), styles["highlight_title"]),
        ]
        meta_parts = [part for part in [highlight.journal, highlight.published] if part]
        if meta_parts:
            inner.append(
                Paragraph(
                    " &nbsp;&middot;&nbsp; ".join(
                        escape(_to_pdf_text(p)).upper() for p in meta_parts
                    ),
                    styles["highlight_meta"],
                )
            )
        if highlight.why_it_matters:
            inner.append(
                Paragraph(
                    f"<b>Why it matters &middot;</b> {escape(_to_pdf_text(highlight.why_it_matters))}",
                    styles["highlight_body"],
                )
            )
        if highlight.link:
            inner.append(
                Paragraph(
                    f"<link href='{escape(highlight.link, quote=True)}'>Open article &rarr;</link>",
                    styles["highlight_link"],
                )
            )
        card = Table(
            [[inner]],
            colWidths=[None],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["surface"])),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor(PALETTE["border"])),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(PALETTE["accent"])),
                    ("LEFTPADDING", (0, 0), (-1, -1), 14),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                    ("TOPPADDING", (0, 0), (-1, -1), 11),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                ]
            ),
        )
        story.append(KeepTogether(card))
        story.append(Spacer(1, 0.08 * inch))
    story.append(Spacer(1, 0.08 * inch))
    return story


def _pdf_toc_block(structured: list[FullDigestSection], styles: dict[str, ParagraphStyle]) -> list:
    if not structured:
        return []
    story: list = [_section_band("Table of Contents", styles)]
    for section in structured:
        story.append(Paragraph(escape(_to_pdf_text(section.name)), styles["toc_section"]))
        for journal in section.journals:
            story.append(
                Paragraph(
                    f"&bull;&nbsp;&nbsp;<link href='#{journal.anchor}'>{escape(_to_pdf_text(journal.name))}</link>",
                    styles["toc_entry"],
                )
            )
    story.append(Spacer(1, 0.16 * inch))
    return story


def _pdf_snapshot_block(items: list[str], styles: dict[str, ParagraphStyle]) -> list:
    story: list = [_section_band("Collection Snapshot", styles)]
    stat_cells: list[tuple[str, str]] = []
    note_items: list[str] = []
    for entry in items:
        label, _, value = entry.partition(":")
        if value:
            stat_cells.append((label.strip(), value.strip()))
        else:
            note_items.append(entry.strip())
    columns = 3
    rows: list[list] = []
    while stat_cells:
        row_chunk = stat_cells[:columns]
        stat_cells = stat_cells[columns:]
        row: list = []
        for label, value in row_chunk:
            cell = [
                Paragraph(escape(_to_pdf_text(label)).upper(), styles["snapshot_label"]),
                Paragraph(escape(_to_pdf_text(value)), styles["snapshot_value"]),
            ]
            row.append(cell)
        while len(row) < columns:
            row.append("")
        rows.append(row)
    if rows:
        column_width = (PAGE_WIDTH - 1.2 * inch) / columns
        snapshot_table = Table(
            rows,
            colWidths=[column_width] * columns,
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["surface_alt"])),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor(PALETTE["border_soft"])),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor(PALETTE["border_soft"])),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            ),
        )
        story.append(KeepTogether(snapshot_table))
    for note in note_items:
        story.append(Spacer(1, 0.05 * inch))
        story.append(Paragraph(escape(_to_pdf_text(note)), styles["snapshot_note"]))
    story.append(Spacer(1, 0.16 * inch))
    return story


def _pdf_full_digest_block(
    structured: list[FullDigestSection], styles: dict[str, ParagraphStyle]
) -> list:
    if not structured:
        return []
    story: list = [PageBreak(), _section_band("Full Curated Digest", styles)]
    for section_index, section in enumerate(structured):
        if section_index > 0:
            story.append(Spacer(1, 0.18 * inch))
        story.append(_digest_section_header(section.name, styles))
        story.append(Spacer(1, 0.1 * inch))
        for journal in section.journals:
            story.append(_journal_header(journal, styles))
            story.append(Spacer(1, 0.05 * inch))
            for article in journal.articles:
                story.extend(_article_card(article, styles))
                story.append(Spacer(1, 0.06 * inch))
            story.append(Spacer(1, 0.06 * inch))
    return story


def _section_band(label: str, styles: dict[str, ParagraphStyle]) -> Table:
    band = Table(
        [[Paragraph(escape(_to_pdf_text(label)).upper(), styles["section_band_label"])]],
        colWidths=[None],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["ink"])),
                ("LINEABOVE", (0, 0), (-1, 0), 0, colors.HexColor(PALETTE["ink"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        ),
    )
    band.spaceAfter = 0.08 * inch
    return band


def _digest_section_header(name: str, styles: dict[str, ParagraphStyle]) -> Table:
    accent_color, tint_color = SECTION_COLOR_MAP.get(name, (PALETTE["ink"], PALETTE["accent_soft"]))
    style = ParagraphStyle(
        f"DigestDigestSectionHeading-{name}",
        parent=styles["digest_section_heading"],
        textColor=colors.HexColor(accent_color),
    )
    return Table(
        [[Paragraph(escape(_to_pdf_text(name)), style)]],
        colWidths=[None],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(tint_color)),
                ("LINEBEFORE", (0, 0), (0, -1), 5, colors.HexColor(accent_color)),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )


def _journal_header(journal: FullDigestJournal, styles: dict[str, ParagraphStyle]) -> Table:
    anchored = f"<a name='{journal.anchor}'/>{escape(_to_pdf_text(journal.name))}"
    return Table(
        [[Paragraph(anchored, styles["journal_heading"])]],
        colWidths=[None],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["accent_soft"])),
                ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(PALETTE["accent"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        ),
    )


def _article_card(article: FullDigestArticle, styles: dict[str, ParagraphStyle]) -> list:
    story: list = [_article_rule()]
    story.extend(
        [
        Paragraph(escape(_to_pdf_text(article.title)), styles["article_title"]),
        ]
    )
    meta_parts: list[str] = []
    if article.published:
        meta_parts.append(escape(_to_pdf_text(article.published)).upper())
    if article.doi:
        meta_parts.append(f"DOI {escape(_to_pdf_text(article.doi)).upper()}")
    if meta_parts:
        story.append(
            Paragraph(
                " &nbsp;&middot;&nbsp; ".join(meta_parts),
                styles["article_meta"],
            )
        )
    if article.authors:
        story.append(
            Paragraph(escape(_to_pdf_text(article.authors)), styles["article_authors"])
        )
    if article.affiliations:
        story.append(
            Paragraph(
                escape(_to_pdf_text(article.affiliations)),
                styles["article_affiliations"],
            )
        )
    if article.abstract:
        story.append(
            Paragraph(
                f"<b>Abstract.</b> {escape(_to_pdf_text(article.abstract))}",
                styles["article_abstract"],
            )
        )
    if article.link:
        story.append(
            Paragraph(
                f"<link href='{escape(article.link, quote=True)}'>Read article &rarr;</link>",
                styles["article_link"],
            )
        )
    return story


def _article_rule() -> Flowable:
    rule = Table(
        [[""]],
        colWidths=[None],
        rowHeights=[1.5],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["border_soft"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )
    rule.spaceAfter = 0.08 * inch
    return rule


def _accent_rule() -> Flowable:
    rule = Table(
        [[""]],
        colWidths=[1.4 * inch],
        rowHeights=[3],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE["accent"])),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        ),
    )
    rule.spaceAfter = 0
    return rule


def _to_pdf_text(text: str) -> str:
    replacements = {
        "–": "-",
        "—": "-",
        "‘": "'",
        "’": "'",
        "“": '"',
        "”": '"',
        "•": "-",
        " ": " ",
    }
    cleaned = text.translate(str.maketrans(replacements))
    normalized = unicodedata.normalize("NFKD", cleaned)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _outline_anchor(section: str, journal: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _to_pdf_text(f"{section}-{journal}").lower()).strip("-")
    if not slug:
        slug = "journal"
    return f"{slug}-{index}"
