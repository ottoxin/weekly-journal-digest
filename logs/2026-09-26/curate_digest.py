"""Reproducible, manually reviewed article selection for the 2026-09-26 edition."""

import json
from collections import defaultdict
from pathlib import Path


root = Path(__file__).resolve().parents[2]
candidate_path = root / "logs/2026-09-26/candidate_digest-2026-09-26.json"
output_path = root / "logs/2026-09-26/reviewed_digest-2026-09-26.structured.md"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
sections = candidate["sections"]

# All substantive communication and political-science journal articles are kept.
# Broad-science selections were individually screened for COMAP relevance.
new_indexes = [
    0,
    7,
    31,
    41,
    42,
    44,
    73,
    76,
    77,
    100,
    101,
    108,
    109,
    111,
    116,
    123,
    124,
    132,
    139,
    144,
]
catch_up_indexes = []
late_indexes = []
highlight_indexes = [111, 109, 124, 42, 100, 108, 41, 76]

why = {
    111: "Separates interaction effects from default-stance, agreement, and anchoring biases in LLM agent discussions, directly testing when synthetic opinion dynamics can stand in for human behavior.",
    109: "Uses online trace data from South Korea and the United States to show how content, source, and cultural context shape rejection of cross-cutting news.",
    124: "Recasts democratic backsliding and resilience as participatory media processes in which ordinary actors, institutions, and anonymous or false-identity accounts jointly shape political change.",
    42: "Longitudinal global evidence links stronger democratic media performance with later gains in electoral, participatory, and deliberative democracy while carefully limiting causal claims.",
    100: "Draws a clear methodological boundary around synthetic respondents, a timely warning for computational social scientists considering LLMs as substitutes for human participants.",
    108: "Connects industrial decline, household breadwinner norms, and right-wing voting through local labor-market and long-run individual evidence.",
    41: "Shows how centralized administrative power can punish electorally oppositional communities, extending presidential particularism from targeted benefits to targeted costs.",
    76: "Combines experiments, psychophysiology, and qualitative interpretation to show how visible facial expression changes the experience of interpersonal distance in virtual reality.",
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
    if not items:
        return
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
    "Subject: Weekly journal digest for 2026-09-21 to 2026-09-26",
    "",
    "## Summary",
    "",
    "This COMAP Journal Bot edition centers on a common problem: how people, institutions, and computational agents form judgments under mediated conditions. New work traces cross-cutting news rejection across cultures, democratic media performance across seven decades, political participation in backsliding and resilience, and the biases that structure simulated opinion dynamics among large language models.",
    "",
    "The broader reading list connects industrial decline to gendered political backlash, administrative power to partisan punishment, and virtual-reality disclosure to embodied communication. Methodological papers on synthetic research participants, interpretable machine learning, and LLM-era reproducibility make this an especially useful week for anyone designing AI-assisted social-science research.",
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
    "- The candidate counts are the complete collected set after automated source filters and before manual relevance review; the full curated list below is the focused subset.",
    "- All 17 article sources completed. Previously delivered September 14–19 papers are not repeated; the newly indexed catch-up and late-addition candidates did not meet the COMAP relevance threshold.",
    "",
    "## Highlights",
    "",
]

for idx in highlight_indexes:
    item = sections["new_this_week"][idx]
    lines.extend(
        [
            f"- **{item['title']}**",
            f"  Journal: {item['journal']}",
            f"  Published: {item['published_date']}",
            f"  Why it matters: {why[idx]}",
            f"  Link: {item['link']}",
            "",
        ]
    )

lines.extend(["## Full Curated Digest", ""])
grouped_section(lines, "New This Week", new)
grouped_section(lines, "Previous Week Catch-Up", catch_up)
grouped_section(lines, "Late Additions", late)
output_path.write_text("\n".join(lines), encoding="utf-8")
print(output_path)
