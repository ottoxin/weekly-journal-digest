from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


BOT_NAME = "COMAP Journal Bot"


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


def render_summary_plain_text(reviewed: ReviewedDigest) -> str:
    lines = [BOT_NAME, "", "Summary", "", reviewed.summary.strip(), "", "Highlights"]
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
    return "\n".join(lines).strip() + "\n"


def render_summary_html(reviewed: ReviewedDigest) -> str:
    summary_html = _render_summary_blocks_html(reviewed.summary)
    highlight_cards = []
    for highlight in reviewed.highlights:
        meta = " | ".join(part for part in [highlight.journal, highlight.published] if part)
        highlight_cards.append(
            "".join(
                [
                    "<div style='border:1px solid #d9e2f0; border-left:4px solid #1f6feb; "
                    "border-radius:10px; padding:14px 16px; margin:0 0 14px 0; background:#ffffff;'>",
                    f"<div style='font-size:16px; font-weight:700; color:#0f172a; margin:0 0 6px 0;'>{escape(highlight.title)}</div>",
                    f"<div style='font-size:13px; color:#52606d; margin:0 0 8px 0;'>{escape(meta)}</div>" if meta else "",
                    f"<div style='font-size:14px; line-height:1.55; color:#243b53; margin:0 0 10px 0;'><strong>Why it matters:</strong> {escape(highlight.why_it_matters)}</div>"
                    if highlight.why_it_matters
                    else "",
                    f"<a href='{escape(highlight.link, quote=True)}' "
                    "style='display:inline-block; padding:8px 12px; background:#1f6feb; color:#ffffff; "
                    "text-decoration:none; border-radius:999px; font-size:13px; font-weight:600;'>Open article</a>"
                    if highlight.link
                    else "",
                    "</div>",
                ]
            )
        )
    return (
        "<html><body style='margin:0; padding:0; background:#eef3f9;'>"
        "<div style='max-width:760px; margin:0 auto; padding:24px 16px;'>"
        "<div style='background:#ffffff; border-radius:18px; padding:28px 28px 20px 28px; "
        "box-shadow:0 10px 30px rgba(15,23,42,0.08);'>"
        f"<div style='font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:#627d98; margin:0 0 10px 0;'>{escape(BOT_NAME)}</div>"
        f"<h1 style='margin:0 0 18px 0; font-size:28px; line-height:1.2; color:#102a43;'>{escape(reviewed.subject)}</h1>"
        f"{summary_html}"
        "<h2 style='margin:26px 0 12px 0; font-size:18px; color:#102a43;'>Highlights</h2>"
        f"{''.join(highlight_cards)}"
        "<div style='margin-top:22px; padding:14px 16px; border-radius:12px; background:#f0f4f8; "
        "color:#334e68; font-size:14px; line-height:1.5;'>"
        "The attached PDF includes the full curated digest, abstract-level details, and a journal table of contents."
        "</div>"
        "</div></div></body></html>"
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
    outline = _build_digest_outline(reviewed.full_curated_digest_markdown)
    story.append(Paragraph(escape(_to_pdf_text(BOT_NAME)), styles["meta"]))
    story.append(Spacer(1, 0.04 * inch))
    story.append(Paragraph(escape(_to_pdf_text(reviewed.subject)), styles["title"]))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("Summary", styles["heading"]))
    story.extend(_render_summary_blocks_pdf(reviewed.summary, styles))
    story.append(Spacer(1, 0.12 * inch))
    if outline:
        story.append(Paragraph("Table of Contents", styles["heading"]))
        for entry in outline:
            story.append(
                Paragraph(
                    f"&#8226; <link href='#{entry.anchor}'>{escape(_to_pdf_text(entry.label))}</link>",
                    styles["bullet"],
                )
            )
        story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("Highlights", styles["heading"]))
    for highlight in reviewed.highlights:
        story.append(Paragraph(escape(_to_pdf_text(highlight.title)), styles["highlight_title"]))
        meta = " | ".join(part for part in [highlight.journal, highlight.published] if part)
        if meta:
            story.append(Paragraph(escape(_to_pdf_text(meta)), styles["meta"]))
        if highlight.why_it_matters:
            story.append(
                Paragraph(
                    f"<b>Why it matters:</b> {escape(_to_pdf_text(highlight.why_it_matters))}",
                    styles["body"],
                )
            )
        if highlight.link:
            story.append(Paragraph(f"<b>Link:</b> {escape(_to_pdf_text(highlight.link))}", styles["body"]))
        story.append(Spacer(1, 0.08 * inch))
    story.append(Spacer(1, 0.12 * inch))
    if reviewed.collection_snapshot:
        story.append(Paragraph("Collection Snapshot", styles["heading"]))
        for item in reviewed.collection_snapshot:
            story.append(Paragraph(f"&#8226; {escape(_to_pdf_text(item))}", styles["bullet"]))
        story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("Full Curated Digest", styles["heading"]))
    story.extend(_render_full_digest_story(reviewed.full_curated_digest_markdown, styles))
    doc.build(story)
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


def _build_digest_outline(markdown: str) -> list[OutlineEntry]:
    outline: list[OutlineEntry] = []
    current_section = ""
    seen: dict[tuple[str, str], int] = {}
    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("### "):
            current_section = stripped[4:].strip()
            continue
        if stripped.startswith("#### "):
            journal = stripped[5:].strip()
            key = (current_section, journal)
            seen[key] = seen.get(key, 0) + 1
            outline.append(
                OutlineEntry(
                    label=f"{current_section}: {journal}" if current_section else journal,
                    anchor=_outline_anchor(current_section, journal, seen[key]),
                )
            )
    return outline


def _build_pdf_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DigestTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=24,
            textColor=colors.HexColor("#102a43"),
            spaceAfter=10,
        ),
        "heading": ParagraphStyle(
            "DigestHeading",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#102a43"),
            spaceBefore=8,
            spaceAfter=6,
        ),
        "highlight_title": ParagraphStyle(
            "DigestHighlightTitle",
            parent=sample["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=3,
        ),
        "meta": ParagraphStyle(
            "DigestMeta",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#52606d"),
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "DigestBody",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#243b53"),
            spaceAfter=5,
        ),
        "bullet": ParagraphStyle(
            "DigestBullet",
            parent=sample["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#243b53"),
            leftIndent=12,
            firstLineIndent=-10,
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
    }


def _render_full_digest_story(markdown: str, styles: dict[str, ParagraphStyle]) -> list:
    story = []
    current_section = ""
    seen: dict[tuple[str, str], int] = {}
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            story.append(Spacer(1, 0.06 * inch))
            continue
        if stripped.startswith("### "):
            current_section = stripped[4:].strip()
            story.append(Paragraph(escape(_to_pdf_text(current_section)), styles["heading"]))
            continue
        if stripped.startswith("#### "):
            journal = stripped[5:].strip()
            key = (current_section, journal)
            seen[key] = seen.get(key, 0) + 1
            anchor = _outline_anchor(current_section, journal, seen[key])
            story.append(
                Paragraph(
                    f"<a name='{anchor}'/>{escape(_to_pdf_text(journal))}",
                    styles["highlight_title"],
                )
            )
            continue
        title_match = re.match(r"^- \*\*(.+?)\*\*$", stripped)
        if title_match:
            story.append(Paragraph(f"&#8226; <b>{escape(_to_pdf_text(title_match.group(1)))}</b>", styles["bullet"]))
            continue
        if stripped.startswith("- "):
            story.append(Paragraph(f"&#8226; {escape(_to_pdf_text(stripped[2:]))}", styles["bullet"]))
            continue
        story.append(Paragraph(escape(_to_pdf_text(stripped)), styles["detail"]))
    return story


def _to_pdf_text(text: str) -> str:
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


def _outline_anchor(section: str, journal: str, index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _to_pdf_text(f"{section}-{journal}").lower()).strip("-")
    if not slug:
        slug = "journal"
    return f"{slug}-{index}"
