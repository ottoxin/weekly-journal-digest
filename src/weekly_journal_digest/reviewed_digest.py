from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from html import escape, unescape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import CondPageBreak, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


BOT_NAME = "COMAP Journal Bot"
UNSUBSCRIBE_EMAIL = "haohangxin@u.northwestern.edu"
UNSUBSCRIBE_TEXT = f"If you wish to unsubscribe, send email to {UNSUBSCRIBE_EMAIL}"
SECTION_PALETTES = {
    "New This Week": {
        "accent": colors.HexColor("#0f766e"),
        "surface": colors.HexColor("#f0fdfa"),
        "border": colors.HexColor("#99f6e4"),
        "title": colors.white,
    },
    "Previous Week Catch-Up": {
        "accent": colors.HexColor("#2563eb"),
        "surface": colors.HexColor("#eff6ff"),
        "border": colors.HexColor("#bfdbfe"),
        "title": colors.white,
    },
    "Late Additions": {
        "accent": colors.HexColor("#b45309"),
        "surface": colors.HexColor("#fffbeb"),
        "border": colors.HexColor("#fcd34d"),
        "title": colors.white,
    },
}
DEFAULT_SECTION_PALETTE = {
    "accent": colors.HexColor("#334155"),
    "surface": colors.HexColor("#f8fafc"),
    "border": colors.HexColor("#cbd5e1"),
    "title": colors.white,
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
    anchor: str


@dataclass(slots=True)
class ReviewedDigest:
    subject: str
    summary: str
    collection_snapshot: list[str]
    highlights: list[Highlight]
    full_curated_digest_markdown: str


@dataclass(slots=True)
class DigestArticle:
    title: str
    published: str = ""
    authors: str = ""
    affiliations: str = ""
    doi: str = ""
    link: str = ""
    abstract: str = ""


@dataclass(slots=True)
class DigestJournal:
    journal: str
    articles: list[DigestArticle]


@dataclass(slots=True)
class DigestSection:
    label: str
    journals: list[DigestJournal]


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
    lines = [f"Dear {_salutation_name(recipient_name)},", "", "Summary", "", reviewed.summary.strip(), "", "Highlights"]
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
    lines.append("The full curated digest is attached as a PDF.")
    lines.extend(["", BOT_NAME, "", UNSUBSCRIBE_TEXT])
    return "\n".join(lines).strip() + "\n"


def render_summary_html(
    reviewed: ReviewedDigest,
    recipient_name: str | None = None,
) -> str:
    summary_html = _render_summary_blocks_html(reviewed.summary)
    highlight_cards = []
    for index, highlight in enumerate(reviewed.highlights, start=1):
        meta = " | ".join(part for part in [highlight.journal, highlight.published] if part)
        highlight_cards.append(
            "".join(
                [
                    "<tr><td style='padding:0 0 14px 0;'>",
                    "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' "
                    "style='border-collapse:separate; border-spacing:0; border:1px solid #d8e2ee; "
                    "border-left:4px solid #0f766e; border-radius:8px; background:#ffffff;'>",
                    "<tr><td style='padding:14px 16px 13px 16px;'>",
                    "<div style='font-size:12px; line-height:1; font-weight:700; color:#0f766e; "
                    f"margin:0 0 7px 0;'>Highlight {index}</div>",
                    f"<div style='font-size:17px; font-weight:700; line-height:1.32; color:#0f172a; margin:0 0 7px 0;'>{escape(highlight.title)}</div>",
                    f"<div style='font-size:13px; line-height:1.45; color:#52606d; margin:0 0 9px 0;'>{escape(meta)}</div>" if meta else "",
                    f"<div style='font-size:14px; line-height:1.58; color:#243b53; margin:0 0 12px 0;'><strong>Why it matters:</strong> {escape(highlight.why_it_matters)}</div>"
                    if highlight.why_it_matters
                    else "",
                    f"<a href='{escape(highlight.link, quote=True)}' "
                    "style='display:inline-block; padding:8px 12px; background:#0f766e; color:#ffffff; "
                    "text-decoration:none; border-radius:6px; font-size:13px; line-height:1; font-weight:700;'>Open article</a>"
                    if highlight.link
                    else "",
                    "</td></tr></table></td></tr>",
                ]
            )
        )
    return (
        "<!doctype html><html><body style='margin:0; padding:0; background:#eef3f9; "
        "font-family:Arial, Helvetica, sans-serif;'>"
        "<div style='display:none; max-height:0; overflow:hidden; color:#eef3f9;'>"
        "Weekly COMAP Journal Bot highlights with the full curated digest attached as a PDF."
        "</div>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='border-collapse:collapse; background:#eef3f9;'>"
        "<tr><td align='center' style='padding:24px 14px;'>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' "
        "style='border-collapse:collapse; max-width:760px; background:#ffffff; border:1px solid #d8e2ee;'>"
        "<tr><td style='padding:26px 28px 18px 28px; background:#f8fafc; border-bottom:1px solid #d8e2ee;'>"
        f"<div style='font-size:12px; line-height:1.2; font-weight:700; text-transform:uppercase; color:#0f766e; margin:0 0 10px 0;'>{escape(BOT_NAME)}</div>"
        f"<h1 style='margin:0; font-size:27px; line-height:1.2; color:#0f172a; font-weight:700;'>{escape(reviewed.subject)}</h1>"
        "</td></tr>"
        "<tr><td style='padding:22px 28px 4px 28px;'>"
        f"<p style='margin:0 0 14px 0; font-size:16px; line-height:1.6; color:#243b53;'>Dear {escape(_salutation_name(recipient_name))},</p>"
        f"{summary_html}"
        "</td></tr>"
        "<tr><td style='padding:10px 28px 0 28px;'>"
        "<h2 style='margin:0 0 14px 0; font-size:19px; line-height:1.3; color:#102a43;'>Highlights</h2>"
        "<table role='presentation' width='100%' cellspacing='0' cellpadding='0' style='border-collapse:collapse;'>"
        f"{''.join(highlight_cards)}"
        "</table>"
        "</td></tr>"
        "<tr><td style='padding:8px 28px 24px 28px;'>"
        "<div style='padding:14px 16px; border:1px solid #c7d2fe; border-radius:8px; background:#eef2ff; "
        "color:#334155; font-size:14px; line-height:1.55;'>"
        "The attached PDF includes the full curated digest, abstract-level details, and a journal table of contents."
        "</div>"
        f"<div style='margin-top:20px; font-size:15px; line-height:1.4; font-weight:700; color:#102a43;'>{escape(BOT_NAME)}</div>"
        f"<div style='margin-top:10px; font-size:12px; line-height:1.5; color:#627d98;'>{escape(UNSUBSCRIBE_TEXT)}</div>"
        "</td></tr>"
        "</table></td></tr></table></body></html>"
    )


def render_curated_digest_pdf(reviewed: ReviewedDigest) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=0.65 * inch,
        rightMargin=0.65 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=_to_pdf_text(reviewed.subject),
    )
    story = []
    styles = _build_pdf_styles()
    sections = _parse_full_curated_digest(reviewed.full_curated_digest_markdown)
    outline = _build_digest_outline_from_sections(sections)
    pdf_highlights = _select_pdf_highlights(reviewed, sections)
    story.append(_render_pdf_header(reviewed.subject, styles, doc.width))
    story.append(Spacer(1, 0.14 * inch))
    story.append(_render_section_banner("Summary", styles, doc.width, SECTION_PALETTES["New This Week"], "weekly brief"))
    story.extend(_render_summary_blocks_pdf(reviewed.summary, styles))
    story.append(Spacer(1, 0.10 * inch))
    if outline:
        story.append(
            _render_section_banner(
                "Table of Contents",
                styles,
                doc.width,
                DEFAULT_SECTION_PALETTE,
                f"{len(outline)} journal sections",
            )
        )
        for entry in outline:
            story.append(_render_toc_entry(entry, styles, doc.width))
        story.append(Spacer(1, 0.12 * inch))
    story.append(
        _render_section_banner(
            "Highlights",
            styles,
            doc.width,
            SECTION_PALETTES["New This Week"],
            f"{len(pdf_highlights)} priority papers",
        )
    )
    story.append(Paragraph("Focused on New This Week.", styles["callout"]))
    for index, highlight in enumerate(pdf_highlights, start=1):
        story.append(_render_highlight_card(highlight, index, styles, doc.width))
        story.append(Spacer(1, 0.08 * inch))
    story.append(Spacer(1, 0.12 * inch))
    if reviewed.collection_snapshot:
        story.append(
            _render_section_banner(
                "Collection Snapshot",
                styles,
                doc.width,
                DEFAULT_SECTION_PALETTE,
                "collected vs curated",
            )
        )
        story.append(_render_collection_snapshot_table(reviewed.collection_snapshot, styles, doc.width))
        story.append(Spacer(1, 0.12 * inch))
    article_count = sum(
        len(journal.articles)
        for section in sections
        for journal in section.journals
    )
    story.append(
        _render_section_banner(
            "Full Curated Digest",
            styles,
            doc.width,
            DEFAULT_SECTION_PALETTE,
            f"{article_count} papers",
        )
    )
    story.extend(_render_full_digest_story(sections, styles, doc.width))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph(escape(_to_pdf_text(UNSUBSCRIBE_TEXT)), styles["fineprint"]))
    doc.build(story, onFirstPage=_draw_pdf_footer, onLaterPages=_draw_pdf_footer)
    return buffer.getvalue()


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


def _paragraphs(text: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text.strip()) if paragraph.strip()]


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


def _salutation_name(recipient_name: str | None) -> str:
    cleaned = " ".join((recipient_name or "").split())
    return cleaned or "Reader"


def _render_summary_blocks_html(text: str) -> str:
    parts: list[str] = []
    for block_type, items in _summary_blocks(text):
        if block_type == "paragraph":
            parts.append(
                f"<p style='margin:0 0 12px 0; line-height:1.65; color:#1f2937;'>{escape(items[0])}</p>"
            )
            continue
        bullet_items = "".join(
            f"<li style='margin:0 0 8px 0;'>{escape(item)}</li>" for item in items
        )
        parts.append(
            "<ul style='margin:0 0 18px 18px; padding:0; color:#243b53; line-height:1.55;'>"
            f"{bullet_items}</ul>"
        )
    return "".join(parts)


def _render_summary_blocks_pdf(text: str, styles: dict[str, ParagraphStyle]) -> list:
    story = []
    for block_type, items in _summary_blocks(text):
        if block_type == "paragraph":
            story.append(Paragraph(escape(_to_pdf_text(items[0])), styles["body"]))
            continue
        for item in items:
            story.append(Paragraph(f"&#8226; {escape(_to_pdf_text(item))}", styles["bullet"]))
    return story


def _build_pdf_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "header_kicker": ParagraphStyle(
            "DigestHeaderKicker",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=10.5,
            textColor=colors.HexColor("#0f766e"),
            alignment=TA_LEFT,
            spaceAfter=0,
        ),
        "header_meta": ParagraphStyle(
            "DigestHeaderMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=10.2,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_RIGHT,
            spaceAfter=0,
        ),
        "header_subtitle": ParagraphStyle(
            "DigestHeaderSubtitle",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=11.5,
            textColor=colors.HexColor("#475569"),
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "title": ParagraphStyle(
            "DigestTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=26,
            textColor=colors.HexColor("#0f172a"),
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "heading": ParagraphStyle(
            "DigestHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=17,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "highlight_title": ParagraphStyle(
            "DigestHighlightTitle",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.8,
            leading=14.5,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=3,
        ),
        "meta": ParagraphStyle(
            "DigestMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=11.5,
            textColor=colors.HexColor("#52606d"),
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "DigestBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14.2,
            textColor=colors.HexColor("#1e293b"),
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "DigestBullet",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=13.5,
            textColor=colors.HexColor("#334155"),
            leftIndent=16,
            firstLineIndent=-12,
            spaceAfter=4,
        ),
        "detail": ParagraphStyle(
            "DigestDetail",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#334e68"),
            leftIndent=14,
            spaceAfter=4,
        ),
        "article_detail": ParagraphStyle(
            "DigestArticleDetail",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.5,
            textColor=colors.HexColor("#334e68"),
            leftIndent=14,
            rightIndent=8,
            spaceAfter=3.5,
        ),
        "article_abstract": ParagraphStyle(
            "DigestArticleAbstract",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13.1,
            textColor=colors.HexColor("#1f2937"),
            leftIndent=14,
            rightIndent=8,
            spaceBefore=2,
            spaceAfter=5,
        ),
        "article_title": ParagraphStyle(
            "DigestArticleTitle",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.4,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=3,
        ),
        "banner": ParagraphStyle(
            "DigestBanner",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14.5,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=0,
        ),
        "section_note": ParagraphStyle(
            "DigestSectionNote",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_RIGHT,
            spaceAfter=0,
        ),
        "callout": ParagraphStyle(
            "DigestCallout",
            parent=sample["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9.2,
            leading=12,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=7,
        ),
        "card_meta": ParagraphStyle(
            "DigestCardMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=11.5,
            textColor=colors.HexColor("#475569"),
            spaceAfter=2,
        ),
        "card_body": ParagraphStyle(
            "DigestCardBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.7,
            leading=13.2,
            textColor=colors.HexColor("#243b53"),
            spaceAfter=3,
        ),
        "link": ParagraphStyle(
            "DigestLink",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=11.5,
            textColor=colors.HexColor("#0f766e"),
            spaceAfter=0,
        ),
        "journal": ParagraphStyle(
            "DigestJournal",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.2,
            leading=13.5,
            textColor=colors.HexColor("#102a43"),
            spaceAfter=0,
        ),
        "journal_count": ParagraphStyle(
            "DigestJournalCount",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.4,
            leading=10,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_RIGHT,
            spaceAfter=0,
        ),
        "toc_section": ParagraphStyle(
            "DigestTocSection",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.3,
            leading=10.5,
            textColor=colors.HexColor("#475569"),
            spaceAfter=0,
        ),
        "toc_journal": ParagraphStyle(
            "DigestTocJournal",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.2,
            leading=11.5,
            textColor=colors.HexColor("#0f766e"),
            spaceAfter=0,
        ),
        "highlight_number": ParagraphStyle(
            "DigestHighlightNumber",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=15,
            textColor=colors.HexColor("#0f766e"),
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "table_header": ParagraphStyle(
            "DigestTableHeader",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=11,
            textColor=colors.HexColor("#334155"),
        ),
        "table_date": ParagraphStyle(
            "DigestTableDate",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.8,
            leading=11,
            textColor=colors.HexColor("#92400e"),
        ),
        "table_title": ParagraphStyle(
            "DigestTableTitle",
            parent=sample["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.1,
            leading=11.5,
            textColor=colors.HexColor("#0f172a"),
        ),
        "table_subtitle": ParagraphStyle(
            "DigestTableSubtitle",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.2,
            leading=10,
            textColor=colors.HexColor("#475569"),
        ),
        "fineprint": ParagraphStyle(
            "DigestFineprint",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
        ),
    }


def _render_full_digest_story(
    sections: list[DigestSection],
    styles: dict[str, ParagraphStyle],
    content_width: float,
) -> list:
    story = []
    seen: dict[tuple[str, str], int] = {}
    for section in sections:
        palette = SECTION_PALETTES.get(section.label, DEFAULT_SECTION_PALETTE)
        section_article_count = sum(len(journal.articles) for journal in section.journals)
        story.append(
            _render_section_banner(
                section.label,
                styles,
                content_width,
                palette,
                f"{section_article_count} papers / {len(section.journals)} journals",
            )
        )
        story.append(Spacer(1, 0.04 * inch))
        for journal in section.journals:
            key = (section.label, journal.journal)
            seen[key] = seen.get(key, 0) + 1
            anchor = _outline_anchor(section.label, journal.journal, seen[key])
            story.append(
                _render_journal_header(
                    journal.journal,
                    len(journal.articles),
                    anchor,
                    styles,
                    content_width,
                    palette,
                )
            )
            story.append(Spacer(1, 0.03 * inch))
            if section.label == "Late Additions":
                story.append(_render_late_additions_table(journal.articles, styles, content_width, palette))
            else:
                include_abstract = section.label == "New This Week"
                for article in journal.articles:
                    story.extend(
                        _render_article_card(
                            article,
                            styles,
                            content_width,
                            palette,
                            include_abstract=include_abstract,
                        )
                    )
                    story.append(Spacer(1, 0.06 * inch))
            story.append(Spacer(1, 0.08 * inch))
    return story


def _render_pdf_header(subject: str, styles: dict[str, ParagraphStyle], content_width: float):
    rows = [
        [
            Paragraph(escape(_to_pdf_text(BOT_NAME.upper())), styles["header_kicker"]),
            Paragraph("Curated research brief", styles["header_meta"]),
        ],
        [Paragraph(escape(_to_pdf_text(subject)), styles["title"]), ""],
        [Paragraph("Summary, highlights, collection snapshot, and full curated digest", styles["header_subtitle"]), ""],
    ]
    table = Table(rows, colWidths=[content_width * 0.58, content_width * 0.42])
    table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 1), (-1, 1)),
                ("SPAN", (0, 2), (-1, 2)),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LINEABOVE", (0, 0), (-1, 0), 3, colors.HexColor("#0f766e")),
                ("LINEBELOW", (0, -1), (-1, -1), 0.8, colors.HexColor("#e2e8f0")),
                ("TOPPADDING", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 1), (-1, 1), 6),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
                ("TOPPADDING", (0, 2), (-1, 2), 1),
                ("BOTTOMPADDING", (0, 2), (-1, 2), 11),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return table


def _draw_pdf_footer(canvas, doc) -> None:
    canvas.saveState()
    page_width, _ = doc.pagesize
    y = 0.45 * inch
    canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, y + 0.15 * inch, page_width - doc.rightMargin, y + 0.15 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(doc.leftMargin, y, _to_pdf_text(BOT_NAME))
    canvas.drawRightString(page_width - doc.rightMargin, y, f"Page {doc.page}")
    canvas.restoreState()


def _render_section_banner(
    label: str,
    styles: dict[str, ParagraphStyle],
    content_width: float,
    palette: dict,
    note: str = "",
):
    rail_width = 0.08 * inch
    title_width = content_width * 0.56
    note_width = content_width - rail_width - title_width
    table = Table(
        [
            [
                "",
                Paragraph(escape(_to_pdf_text(label)), styles["banner"]),
                Paragraph(escape(_to_pdf_text(note)), styles["section_note"]),
            ]
        ],
        colWidths=[rail_width, title_width, note_width],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), palette["accent"]),
                ("BACKGROUND", (1, 0), (-1, -1), palette["surface"]),
                ("BOX", (0, 0), (-1, -1), 0.8, palette["border"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 0),
                ("LEFTPADDING", (1, 0), (-1, -1), 10),
                ("RIGHTPADDING", (1, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _render_toc_entry(entry: OutlineEntry, styles: dict[str, ParagraphStyle], content_width: float):
    section_label, separator, journal = entry.label.partition(": ")
    journal_label = journal if separator else entry.label
    table = Table(
        [
            [
                Paragraph(escape(_to_pdf_text(section_label)), styles["toc_section"]),
                Paragraph(
                    f"<link href='#{entry.anchor}'>{escape(_to_pdf_text(journal_label))}</link>",
                    styles["toc_journal"],
                ),
            ]
        ],
        colWidths=[content_width * 0.34, content_width * 0.66],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return table


def _render_highlight_card(
    highlight: Highlight,
    index: int,
    styles: dict[str, ParagraphStyle],
    content_width: float,
):
    lines = [
        Paragraph(escape(_to_pdf_text(highlight.title)), styles["highlight_title"]),
    ]
    meta = " | ".join(part for part in [highlight.journal, highlight.published] if part)
    if meta:
        lines.append(Paragraph(escape(_to_pdf_text(meta)), styles["card_meta"]))
    if highlight.why_it_matters:
        lines.append(
            Paragraph(
                f"<b>Why it matters:</b> {escape(_to_pdf_text(highlight.why_it_matters))}",
                styles["card_body"],
            )
        )
    if highlight.link:
        lines.append(
            Paragraph(
                f"<link href='{escape(highlight.link, quote=True)}'>Open article</link>",
                styles["link"],
            )
        )
    table = Table(
        [[Paragraph(str(index), styles["highlight_number"]), lines]],
        colWidths=[0.42 * inch, content_width - 0.42 * inch],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0fdfa")),
                ("BACKGROUND", (1, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#ccfbf1")),
                ("LINEAFTER", (0, 0), (0, -1), 0.6, colors.HexColor("#99f6e4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (0, -1), 8),
                ("RIGHTPADDING", (0, 0), (0, -1), 8),
                ("LEFTPADDING", (1, 0), (-1, -1), 12),
                ("RIGHTPADDING", (1, 0), (-1, -1), 12),
            ]
        )
    )
    return table


def _render_collection_snapshot_table(
    snapshot_items: list[str],
    styles: dict[str, ParagraphStyle],
    content_width: float,
):
    rows = []
    for item in snapshot_items:
        label, _, value = item.partition(":")
        rows.append(
            [
                Paragraph(escape(_to_pdf_text(label.strip() + ":")), styles["table_header"]),
                Paragraph(escape(_to_pdf_text(value.strip())), styles["body"]),
            ]
        )
    table = Table(rows, colWidths=[content_width * 0.38, content_width * 0.62])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#cbd5e1")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#334155")),
                ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _render_journal_header(
    journal: str,
    article_count: int,
    anchor: str,
    styles: dict[str, ParagraphStyle],
    content_width: float,
    palette: dict,
):
    count_label = "1 paper" if article_count == 1 else f"{article_count} papers"
    table = Table(
        [
            [
                Paragraph(f"<a name='{anchor}'/>{escape(_to_pdf_text(journal))}", styles["journal"]),
                Paragraph(count_label, styles["journal_count"]),
            ]
        ],
        colWidths=[content_width * 0.78, content_width * 0.22],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["surface"]),
                ("LINEABOVE", (0, 0), (-1, 0), 1, palette["accent"]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.6, palette["border"]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _render_article_card(
    article: DigestArticle,
    styles: dict[str, ParagraphStyle],
    content_width: float,
    palette: dict,
    *,
    include_abstract: bool,
):
    header_lines = [Paragraph(escape(_to_pdf_text(article.title)), styles["article_title"])]
    meta_bits = [bit for bit in [article.published, article.authors] if bit]
    if meta_bits:
        header_lines.append(Paragraph(escape(_to_pdf_text(" | ".join(meta_bits))), styles["card_meta"]))
    header = Table([[header_lines]], colWidths=[content_width])
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfdff")),
                ("BOX", (0, 0), (-1, -1), 0.7, palette["border"]),
                ("LINEBEFORE", (0, 0), (0, -1), 3, palette["accent"]),
                ("TOPPADDING", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 11),
                ("RIGHTPADDING", (0, 0), (-1, -1), 11),
            ]
        )
    )
    flowables = [CondPageBreak(1.3 * inch), KeepTogether([header]), Spacer(1, 0.035 * inch)]
    if article.affiliations:
        flowables.append(
            Paragraph(
                f"<b>Affiliations:</b> {escape(_to_pdf_text(article.affiliations))}",
                styles["article_detail"],
            )
        )
    if article.doi:
        flowables.append(Paragraph(f"<b>DOI:</b> {escape(_to_pdf_text(article.doi))}", styles["article_detail"]))
    if article.link:
        flowables.append(
            Paragraph(
                f"<b>Link:</b> <link href='{escape(article.link, quote=True)}'>Open article</link>",
                styles["article_detail"],
            )
        )
    if include_abstract and article.abstract:
        flowables.append(
            Paragraph(f"<b>Abstract:</b> {escape(_to_pdf_text(article.abstract))}", styles["article_abstract"])
        )
    elif article.abstract:
        flowables.append(
            Paragraph(
                f"<b>Abstract:</b> {escape(_to_pdf_text(_truncate_text(article.abstract, 280)))}",
                styles["article_abstract"],
            )
        )
    return flowables


def _render_late_additions_table(
    articles: list[DigestArticle],
    styles: dict[str, ParagraphStyle],
    content_width: float,
    palette: dict,
):
    rows = [
        [
            Paragraph("Date", styles["table_header"]),
            Paragraph("Late additions", styles["table_header"]),
            Paragraph("Link", styles["table_header"]),
        ]
    ]
    for article in articles:
        title_parts = [Paragraph(escape(_to_pdf_text(article.title)), styles["table_title"])]
        subtitle_bits = [bit for bit in [article.authors, article.doi or article.abstract] if bit]
        if subtitle_bits:
            title_parts.append(
                Paragraph(
                    escape(_to_pdf_text(_truncate_text(" | ".join(subtitle_bits), 210))),
                    styles["table_subtitle"],
                )
            )
        link_target = article.link or (f"https://doi.org/{article.doi}" if article.doi else "")
        link_cell = (
            Paragraph(
                f"<link href='{escape(link_target, quote=True)}'>Open</link>",
                styles["link"],
            )
            if link_target
            else Paragraph("-", styles["table_subtitle"])
        )
        rows.append(
            [
                Paragraph(escape(_to_pdf_text(article.published or "-")), styles["table_date"]),
                title_parts,
                link_cell,
            ]
        )
    table = Table(
        rows,
        colWidths=[content_width * 0.16, content_width * 0.67, content_width * 0.17],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["surface"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("BOX", (0, 0), (-1, -1), 0.8, palette["border"]),
                ("LINEABOVE", (0, 0), (-1, 0), 1, palette["accent"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff7ed")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def _parse_full_curated_digest(markdown: str) -> list[DigestSection]:
    sections: list[DigestSection] = []
    current_section: DigestSection | None = None
    current_journal: DigestJournal | None = None
    current_article: DigestArticle | None = None
    last_field: str | None = None

    def ensure_misc_journal(name: str = "Miscellaneous") -> DigestJournal:
        nonlocal current_journal
        if current_section is None:
            raise ValueError("Digest section is required before journal content.")
        if current_journal is None:
            current_journal = DigestJournal(journal=name, articles=[])
            current_section.journals.append(current_journal)
        return current_journal

    def flush_article() -> None:
        nonlocal current_article, last_field
        if current_article is not None and current_article.title:
            ensure_misc_journal().articles.append(current_article)
        current_article = None
        last_field = None

    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            flush_article()
            current_section = DigestSection(label=stripped[4:].strip(), journals=[])
            sections.append(current_section)
            current_journal = None
            continue
        if stripped.startswith("#### "):
            flush_article()
            if current_section is None:
                current_section = DigestSection(label="Full Curated Digest", journals=[])
                sections.append(current_section)
            current_journal = DigestJournal(journal=stripped[5:].strip(), articles=[])
            current_section.journals.append(current_journal)
            continue
        title_match = re.match(r"^- \*\*(.+?)\*\*$", stripped)
        if title_match:
            flush_article()
            current_article = DigestArticle(title=title_match.group(1).strip())
            ensure_misc_journal()
            continue
        if stripped.startswith("- ") and current_article is None and " | " in stripped:
            parts = [part.strip() for part in stripped[2:].split(" | ")]
            if len(parts) >= 4:
                journal_name, published, title, link = parts[:4]
                if current_section is None:
                    current_section = DigestSection(label="Full Curated Digest", journals=[])
                    sections.append(current_section)
                if current_journal is None or current_journal.journal != journal_name:
                    current_journal = DigestJournal(journal=journal_name, articles=[])
                    current_section.journals.append(current_journal)
                current_journal.articles.append(
                    DigestArticle(
                        title=title,
                        published=published,
                        link=link,
                    )
                )
                continue
        if current_article is None:
            continue
        field_map = {
            "Published: ": "published",
            "Authors: ": "authors",
            "Affiliations: ": "affiliations",
            "DOI: ": "doi",
            "Link: ": "link",
            "Abstract: ": "abstract",
        }
        matched = False
        for prefix, field_name in field_map.items():
            if stripped.startswith(prefix):
                setattr(current_article, field_name, stripped.removeprefix(prefix).strip())
                last_field = field_name
                matched = True
                break
        if matched:
            continue
        if last_field is not None:
            existing = getattr(current_article, last_field)
            setattr(current_article, last_field, f"{existing} {stripped}".strip())
    flush_article()
    return sections


def _build_digest_outline_from_sections(sections: list[DigestSection]) -> list[OutlineEntry]:
    outline: list[OutlineEntry] = []
    seen: dict[tuple[str, str], int] = {}
    for section in sections:
        for journal in section.journals:
            key = (section.label, journal.journal)
            seen[key] = seen.get(key, 0) + 1
            outline.append(
                OutlineEntry(
                    label=f"{section.label}: {journal.journal}",
                    anchor=_outline_anchor(section.label, journal.journal, seen[key]),
                )
            )
    return outline


def _select_pdf_highlights(reviewed: ReviewedDigest, sections: list[DigestSection]) -> list[Highlight]:
    new_titles = {
        article.title
        for section in sections
        if section.label == "New This Week"
        for journal in section.journals
        for article in journal.articles
    }
    prioritized = [highlight for highlight in reviewed.highlights if highlight.title in new_titles]
    return prioritized or reviewed.highlights


def _to_pdf_text(text: str) -> str:
    text = unescape(text)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
    }
    cleaned = text.translate(str.maketrans(replacements))
    normalized = unicodedata.normalize("NFKD", cleaned)
    return normalized.encode("ascii", "ignore").decode("ascii")


def _truncate_text(text: str, limit: int) -> str:
    compact = " ".join(_to_pdf_text(text).split())
    if len(compact) <= limit:
        return compact
    truncated = compact[: limit - 3].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "..."


def _outline_anchor(section: str, journal: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _to_pdf_text(f"{section}-{journal}").lower()).strip("-")
    if not slug:
        slug = "journal"
    return f"{slug}-{index}"
