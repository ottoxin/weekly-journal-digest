"""Reproducible editorial selection for the Saturday October 10 production edition."""

import json
import re
from collections import defaultdict
from pathlib import Path


folder = Path(__file__).resolve().parent
root = folder.parents[1]
candidate_path = folder / "candidate_digest-2026-10-10.json"
output_path = folder / "reviewed_digest-2026-10-10.structured.md"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
sections = candidate["sections"]
previous_markdown = (root / "logs/2026-10-03/reviewed_digest-2026-10-03.structured.md").read_text(encoding="utf-8")
previous_dois = {doi.lower() for doi in re.findall(r"^  DOI: (.+)$", previous_markdown, re.MULTILINE)}

# Indexes are pinned to the fresh post-cutoff candidate generated on 2026-10-10.
selection = {
    "new_this_week": [28, 40, 56, 57, 58, 59, 67, 68, 75, 89, 111, 120, 132, 156, 165, 166, 173],
    "previous_week_catch_up": [33],
    "late_additions": [],
}
highlight_indexes = [166, 165, 68, 59, 56, 120, 28, 173]
why = {
    166: "Audits what brand-new, nonpartisan TikTok accounts encounter before German elections and finds that unsolicited political exposure disproportionately features and supports the far-right AfD.",
    165: "Places algorithm-assisted personalization directly inside vaccination risk communication across three randomized field trials, linking AI-mediated messaging to consequential health behavior.",
    68: "Simulates thousands of networked LLM agents across several model families to study how homophily, confirmation bias, and interaction structure can produce political polarization.",
    59: "Uses two preregistered studies of AI-mediated apologies and gratitude to show how disclosed AI involvement changes perceived sincerity and later relational judgments.",
    56: "Connects classroom history narratives to contemporary foreign-policy attitudes using evidence from 34 classrooms in Seoul, clarifying how institutionalized memory shapes cooperation and conflict.",
    120: "Combines a preregistered urban survey with five election-study waves to distinguish how victimization, local crime, and perceived safety affect turnout and nonelectoral participation.",
    28: "Uses gasoline-price shocks, smartphone mobility traces, and administrative records to estimate how prison visitation affects misconduct and institutional safety.",
    173: "Audits open-source autonomous AI scientist systems and shows why benchmark choice, leakage, metric misuse, and post hoc selection require workflow-level rather than manuscript-only review.",
}

broad_reasons = {
    ("new_this_week", 28): "Quasi-experimental study of social connection, incarceration, violence and institutional policy.",
    ("new_this_week", 40): "Computational signed-network method applied to social-political systems and online social networks.",
    ("new_this_week", 67): "Computational behavioral-model validation for separating learning asymmetry from perseveration and reducing spurious inference.",
    ("new_this_week", 68): "LLM-agent political opinion dynamics, polarization and network interventions; directly aligned with AI for computational social science.",
    ("new_this_week", 89): "Large phone-free classroom experiment on technology, learning and policy; abstract metadata is limited to the supplied one-line summary.",
    ("new_this_week", 111): "Newsroom AI and behavioral evaluation; directly relevant to computational media despite unavailable abstract metadata.",
    ("new_this_week", 132): "Computational analysis of 90,000 scientific and policy documents to study the limits of international conservation governance.",
    ("new_this_week", 156): "Longitudinal urban environmental inequality and equitable climate-adaptation policy across 55 U.S. cities.",
    ("new_this_week", 165): "Algorithm-assisted personalized risk communication tested in three randomized field trials; abstract unavailable in the candidate metadata.",
    ("new_this_week", 173): "Systematic validation and auditing of autonomous AI-scientist workflows, directly relevant to AI-enabled research infrastructure.",
    ("previous_week_catch_up", 33): "Multimodal speech measurement across five countries linking acoustic and linguistic features to dementia, social exposome and aging.",
}

dedicated = {
    "Journal of Communication", "Journal of Computer-Mediated Communication",
    "Political Communication", "Human Communication Research", "Communication Research",
    "Communication Methods and Measures", "American Journal of Political Science",
    "American Political Science Review", "Political Analysis",
}
dedicated_noise = {
    "10.1080/19312458.2026.2742796",  # farewell/editorial
    "10.1017/pan.2026.10052",  # corrigendum
}

kept = {key: [sections[key][index] for index in indexes] for key, indexes in selection.items()}
for key, items in sections.items():
    for index, item in enumerate(items):
        doi = (item.get("doi") or "").lower()
        if item["journal"] in dedicated and doi not in previous_dois and doi not in dedicated_noise:
            assert index in selection[key], ("Unreviewed dedicated-journal article", key, index, item["title"])
for items in kept.values():
    for item in items:
        assert (item.get("doi") or "").lower() not in previous_dois, item["title"]


def article_lines(item):
    result = [f"- **{item['title']}**", f"  Published: {item['published_date']}"]
    if item.get("authors"):
        result.append("  Authors: " + "; ".join(item["authors"]))
    if item.get("affiliations"):
        result.append("  Affiliations: " + "; ".join(item["affiliations"]))
    if item.get("doi"):
        result.append("  DOI: " + item["doi"])
    result.extend(["  Link: " + item["link"], "  Abstract: " + (item.get("abstract") or "Abstract unavailable.")])
    return result


def grouped_section(lines, heading, items):
    if not items:
        return
    lines.extend(["### " + heading, ""])
    by_journal = defaultdict(list)
    for item in items:
        by_journal[item["journal"]].append(item)
    for journal in sorted(by_journal):
        lines.extend(["#### " + journal, ""])
        for item in by_journal[journal]:
            lines.extend(article_lines(item) + [""])


counts = {key: len(items) for key, items in sections.items()}
curated_counts = {key: len(items) for key, items in kept.items()}
lines = [
    "Subject: Weekly journal digest for 2026-10-05 to 2026-10-10", "",
    "## Summary", "",
    "This week, COMAP Journal Bot follows the politics of feeds, memories, and institutional judgment. A TikTok audit tracks the partisan imbalance encountered by new nonpartisan users before German elections; school-history research shows how national narratives shape present-day foreign-policy attitudes; and new work on crime, climate justice, clientelism, and collective action examines when institutions mobilize, exclude, or redirect public participation.", "",
    "The computational reading is unusually cohesive. Networked LLM agents develop polarized political opinions, AI-mediated apologies and gratitude alter judgments of sincerity, personalized algorithms enter vaccination risk communication, and an audit of autonomous AI scientists exposes research flaws that final manuscripts can conceal. Complementary studies sharpen behavioral-model validation, signed-network analysis, prison-visitation policy, newsroom AI evaluation, environmental governance, and urban heat inequality.", "",
    "You may have received two September 7 emails because the first was sent before that collection window closed; the second completed the same edition. Saturday delivery now aligns collection and sending, so each future email represents a distinct Monday–Saturday edition.", "",
    "## Collection Snapshot", "",
    f"- Total collected candidates: {sum(counts.values())}",
    f"- New This Week candidates: {counts['new_this_week']}",
    f"- Previous Week Catch-Up candidates: {counts['previous_week_catch_up']}",
    f"- Late Additions candidates: {counts['late_additions']}",
    f"- Curated digest below: {curated_counts['new_this_week']} new, {curated_counts['previous_week_catch_up']} catch-up, {curated_counts['late_additions']} late additions",
    "- The full collected set above passed automatic source filters and precedes manual relevance review; the curated digest applies the stricter COMAP threshold.",
    "- All 17 article sources completed for the 2026-09-13 through 2026-10-10 collection window, with no source failures or recorded optional-enrichment errors.",
    "- October 3 selections are not repeated. The catch-up paper was newly indexed after that edition.",
    "",
    "## Highlights", "",
]
for index in highlight_indexes:
    item = sections["new_this_week"][index]
    lines.extend([
        f"- **{item['title']}**", f"  Journal: {item['journal']}",
        f"  Published: {item['published_date']}", f"  Why it matters: {why[index]}",
        f"  Link: {item['link']}", "",
    ])
lines.extend(["## Full Curated Digest", ""])
for key, heading in [
    ("new_this_week", "New This Week"),
    ("previous_week_catch_up", "Previous Week Catch-Up"),
    ("late_additions", "Late Additions"),
]:
    grouped_section(lines, heading, kept[key])
output_path.write_text("\n".join(lines), encoding="utf-8")

audit = []
for key, items in sections.items():
    for index, item in enumerate(items):
        selected = index in selection[key]
        doi = (item.get("doi") or "").lower()
        delivered = doi in previous_dois
        reason = broad_reasons.get((key, index))
        if selected and not reason:
            reason = "Substantive dedicated communication or political-science article; retained."
        elif not selected:
            if delivered:
                reason = "Already delivered in the October 3 edition."
            elif doi in dedicated_noise:
                reason = "Non-substantive publication noise (editorial/farewell or corrigendum)."
            else:
                reason = "Outside the strict COMAP relevance threshold: natural science, clinical research, technical AI without a social-science application, or non-substantive publication noise."
        audit.append({
            "section": key, "index": index, "doi": item.get("doi"),
            "title": item["title"], "kept": selected, "reason": reason,
        })
report = {
    "digest_date": "2026-10-10", "prepared_on": "2026-10-10",
    "delivery_status": "production_pending", "preliminary": False,
    "requires_post_cutoff_collection": False, "windows": candidate["windows"],
    "candidate_counts": counts, "curated_counts": curated_counts,
    "highlights": len(highlight_indexes),
    "unavailable_abstracts": [
        {"section": key, "title": item["title"], "doi": item.get("doi")}
        for key, items in kept.items() for item in items
        if not item.get("abstract") or item.get("abstract") == "Abstract unavailable."
    ],
    "missing_authors": [
        {"section": key, "title": item["title"], "doi": item.get("doi")}
        for key, items in kept.items() for item in items if not item.get("authors")
    ],
    "missing_affiliations": [
        {"section": key, "title": item["title"], "doi": item.get("doi")}
        for key, items in kept.items() for item in items if not item.get("affiliations")
    ],
    "decisions": audit,
}
(folder / "curation_audit.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(json.dumps({
    "candidate_counts": counts, "curated_counts": curated_counts,
    "highlights": len(highlight_indexes),
    "missing_abstracts": len(report["unavailable_abstracts"]),
    "missing_authors": len(report["missing_authors"]),
    "missing_affiliations": len(report["missing_affiliations"]),
}))
print(output_path)
