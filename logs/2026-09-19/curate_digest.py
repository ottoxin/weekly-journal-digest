"""Reproducible, manually reviewed article selection for the 2026-09-19 edition."""

import json
from collections import defaultdict
from pathlib import Path


root = Path(__file__).resolve().parents[2]
candidate_path = root / "logs/2026-09-19/candidate_digest-2026-09-19.json"
output_path = root / "logs/2026-09-19/reviewed_digest-2026-09-19.structured.md"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
sections = candidate["sections"]

# Every substantive dedicated communication/political-science article is kept.
# Broad-science selections were individually screened for COMAP relevance.
new_indexes = [0, 11, 12, 42, 45, 50, 61, 67, 70, 85, 105, 132, 133, 156, 159, 162]
catch_up_indexes = [13]  # Newly indexed since the delivered September 12 edition.
late_indexes = [0]
highlight_indexes = [162, 105, 42, 85, 156, 12, 132, 50]

why = {
    162: "A randomized experiment shows that covertly misaligned AI advice can move preferences toward inferior choices while users still rate the advisor as helpful—a direct warning for AI-mediated influence.",
    105: "Combines interviews with 4.5 million Brazilian parliamentary posts to show how platform engagement rewards antagonism and crowds out communication about legislative work.",
    42: "Links political efficacy to what people select from an algorithmic news feed over time, revealing a widening gap in source diversity between users.",
    85: "Validates a direct survey measure of white-nationalist support and connects it to hardship, political disaffection, and primarily online friendships.",
    156: "Panel evidence associates a do-your-own-research mindset with lower nonpartisan news use, poorer belief accuracy, and more hostile views of the media.",
    12: "Uses nearly 47,000 standardized South Korean campaign booklets to isolate how office type and electoral level shape gendered political messaging.",
    132: "A 100-culture study replaces a fuzzy collectivism measure with a responsibility-based scale that better predicts social and political differences.",
    50: "Shows that opaque indicator choices in environmental-justice screening tools change which communities qualify for policy benefits—a measurement-governance problem.",
}


def article_lines(item):
    lines = [f"- **{item['title']}**", f"  Published: {item['published_date']}"]
    if item.get("authors"):
        lines.append("  Authors: " + "; ".join(item["authors"]))
    if item.get("affiliations"):
        lines.append("  Affiliations: " + "; ".join(item["affiliations"]))
    if item.get("doi"):
        lines.append(f"  DOI: {item['doi']}")
    lines.append(f"  Link: {item['link']}")
    lines.append(f"  Abstract: {item.get('abstract') or 'Abstract unavailable.'}")
    return lines


def grouped_section(lines, heading, items):
    lines.extend([f"### {heading}", ""])
    by_journal = defaultdict(list)
    for item in items:
        by_journal[item["journal"]].append(item)
    for journal in sorted(by_journal):
        lines.extend([f"#### {journal}", ""])
        for item in by_journal[journal]:
            lines.extend(article_lines(item))
            lines.append("")


new = [sections["new_this_week"][idx] for idx in new_indexes]
catch_up = [sections["previous_week_catch_up"][idx] for idx in catch_up_indexes]
late = [sections["late_additions"][idx] for idx in late_indexes]
counts = {name: len(items) for name, items in sections.items()}

lines = [
    "Subject: Weekly journal digest for 2026-09-14 to 2026-09-19",
    "",
    "## Summary",
    "",
    "This COMAP Journal Bot edition follows how political messages move through algorithmic feeds, how institutions reward viral confrontation, and how AI can quietly reshape judgment. New work on campaign language, white-nationalist support, and public distrust of expertise gives the week a strong political-communication core; careful measurement studies provide useful tools for the next research question.",
    "",
    "The reading list also includes one political-participation paper newly indexed from September 7–13 and one late-indexed study of bias-like processing in reasoning models. Papers already delivered in the September 12 edition are not repeated here.",
    "",
    "You may have received two September 7 emails because the first was sent before that collection window closed; the second completed the same edition. Saturday delivery now aligns collection and sending, so each future email represents a distinct Monday–Saturday edition.",
    "",
    "## Collection Snapshot",
    "",
    f"- Total collected candidates: {sum(counts.values())}",
    f"- New This Week candidates: {counts['new_this_week']}",
    f"- Previous Week Catch-Up candidates: {counts['previous_week_catch_up']}",
    f"- Late Additions candidates: {counts['late_additions']}",
    f"- Curated digest below: {len(new)} new, {len(catch_up)} catch-up, {len(late)} late additions",
    "- The candidate counts are after automatic source filters and before manual relevance review; the full curated list below is a focused subset.",
    "- All 17 article sources completed; the September 7–13 catch-up candidates already delivered on September 12 are omitted to avoid duplicate reading.",
    "",
    "## Highlights",
    "",
]

for idx in highlight_indexes:
    item = sections["new_this_week"][idx]
    lines.extend([
        f"- **{item['title']}**",
        f"  Journal: {item['journal']}",
        f"  Published: {item['published_date']}",
        f"  Why it matters: {why[idx]}",
        f"  Link: {item['link']}",
        "",
    ])

lines.extend(["## Full Curated Digest", ""])
grouped_section(lines, "New This Week", new)
grouped_section(lines, "Previous Week Catch-Up", catch_up)
grouped_section(lines, "Late Additions", late)
output_path.write_text("\n".join(lines), encoding="utf-8")
print(output_path)
