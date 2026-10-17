"""Reproducible editorial selection for the preliminary October 3 edition."""

import json
import re
from collections import defaultdict
from pathlib import Path


folder = Path(__file__).resolve().parent
root = folder.parents[2]
candidate_path = folder / "candidate_digest-2026-10-03.json"
output_path = folder / "reviewed_digest-2026-10-03.structured.md"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
sections = candidate["sections"]
previous_markdown = (root / "logs/2026-09-26/reviewed_digest-2026-09-26.structured.md").read_text(encoding="utf-8")
previous_dois = {doi.lower() for doi in re.findall(r"^  DOI: (.+)$", previous_markdown, re.MULTILINE)}

selection = {
    "new_this_week": [0, 1, 7, 16, 18, 22, 25, 68, 69, 70, 71, 72, 76, 87, 92, 104, 111, 112],
    "previous_week_catch_up": [2, 4, 40, 48, 88, 89, 142, 159, 160, 161],
    "late_additions": [],
}
highlight_indexes = [104, 71, 0, 68, 111, 7, 16, 87]
why = {
    104: "Models the decision strategies individuals use in political conjoint experiments, showing why aggregate attribute effects can conceal different heuristics and preferences.",
    71: "Tests how counter-speech and accuracy cues shape minority groups' responses to online hate speech, connecting platform interventions with injustice, efficacy, and collective action.",
    0: "Shows how minority representation can simultaneously fragment minority votes and consolidate majority support, using elections, surveys, interviews, and a vignette experiment in India.",
    68: "Explains why shared responsibility between citizens and politicians can complicate blame and electoral accountability even when policy reform has good prospects.",
    111: "Finds that the estimated earnings return to citizenship depends strongly on research design, with a randomized study near zero despite a positive pooled average.",
    7: "Reexamines extreme-heat estimates with spatial and temporal dependence, postselection correction, and out-of-sample prediction, offering a concrete lesson in uncertainty and robustness.",
    16: "Compares narrative and non-narrative inoculation messages in a randomized experiment, clarifying how message format and baseline beliefs affect resistance to conflicting information.",
    87: "Treats communication media as a personal system of strong and weak ties, linking its configuration to distinct sources of digital stress and well-being.",
}

broad_reasons = {
    ("new_this_week", 1): "Human group motives and gender; abstract unavailable, retained on its clearly social-science scope without invented results.",
    ("new_this_week", 7): "Social-science inference and climate-economy policy measurement.",
    ("new_this_week", 18): "Regulatory implementation costs and disproportionate burdens on small/rural water utilities; secondary policy relevance.",
    ("new_this_week", 25): "Political formation and defensive cooperation measured with satellite-derived spatial networks.",
    ("new_this_week", 72): "AI research governance and institutional measurement incentives; abstract unavailable.",
    ("new_this_week", 76): "Cross-cultural institutions, marriage and wealth transmission using Bayesian multilevel models.",
    ("new_this_week", 92): "Human planning and strategy choice under uncertainty using computational cognitive models.",
    ("new_this_week", 104): "Political conjoint measurement and individual decision strategies.",
    ("new_this_week", 111): "Citizenship, migration and causal inference in a quantitative meta-analysis.",
    ("new_this_week", 112): "Scientific attention, information priorities and climate-risk governance.",
    ("previous_week_catch_up", 2): "Replication/reanalysis of a poverty-related attention hypothesis; newly indexed since prior candidate.",
    ("previous_week_catch_up", 40): "Policy interpretation of alternatives-to-policing metrics; previously undelivered commentary.",
    ("previous_week_catch_up", 48): "Preregistered human social-proximity experiments; a secondary, borderline interpersonal-behavior selection.",
    ("previous_week_catch_up", 88): "Digital governance perspective; abstract unavailable.",
    ("previous_week_catch_up", 89): "Political screening of scientific grants and freedom of speech; relevant science-policy reporting.",
    ("previous_week_catch_up", 142): "Communication constraints and echo-chamber dynamics; theoretical biological-agent model, not direct human evidence.",
    ("previous_week_catch_up", 159): "Meritocracy and inequality acceptance; abstract unavailable.",
    ("previous_week_catch_up", 160): "Gender quotas and representation; abstract unavailable.",
    ("previous_week_catch_up", 161): "Structural and psychological inequality; abstract unavailable.",
}
dedicated = {
    "Journal of Communication", "Journal of Computer-Mediated Communication",
    "Political Communication", "Human Communication Research", "Communication Research",
    "Communication Methods and Measures", "American Journal of Political Science",
    "American Political Science Review", "Political Analysis",
}

kept = {key: [sections[key][index] for index in indexes] for key, indexes in selection.items()}
for key, items in sections.items():
    for index, item in enumerate(items):
        if item["journal"] in dedicated and item.get("doi", "").lower() not in previous_dois:
            assert index in selection[key], ("Unreviewed dedicated-journal article", key, index, item["title"])
for items in kept.values():
    for item in items:
        assert item.get("doi", "").lower() not in previous_dois, item["title"]


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
    "Subject: Weekly journal digest for 2026-09-28 to 2026-10-03", "",
    "## Summary", "",
    "This COMAP Journal Bot draft examines how messages, group identities, and institutions shape collective choices. New studies connect online hate speech and counter-speech to minority collective action, trace the electoral consequences of minority representation in India, and examine how shared responsibility between citizens and politicians complicates democratic accountability. Work on personal media systems and inoculation messages brings the same questions into everyday communication and belief formation.", "",
    "The methods reading is especially useful this week: political conjoint experiments reveal individual differences in decision strategies, a citizenship meta-analysis exposes the importance of identification design, and an extreme-heat reanalysis tests how dependence and model selection alter uncertainty. Previously undelivered catch-up papers extend the discussion to scarcity, digital governance, inequality, and collective information dynamics.", "",
    "Preliminary review copy prepared on 2026-10-02 for the 2026-10-03 edition. The nominal New This Week window is 2026-09-28 through 2026-10-03, but Saturday collection is not yet complete. Delivery is held; a fresh collection and candidate build are required after the Saturday cutoff before production delivery.", "",
    "You may have received two September 7 emails because the first was sent before that collection window closed; the second completed the same edition. Saturday delivery now aligns collection and sending, so each future email represents a distinct Monday–Saturday edition.", "",
    "## Collection Snapshot", "",
    f"- Total collected candidates: {sum(counts.values())}",
    f"- New This Week candidates: {counts['new_this_week']}",
    f"- Previous Week Catch-Up candidates: {counts['previous_week_catch_up']}",
    f"- Late Additions candidates: {counts['late_additions']}",
    "- Curated digest below: 18 new, 10 catch-up, 0 late additions",
    "- Candidate counts reflect the complete collected set after automated source filters and before manual relevance review; this is a preliminary snapshot collected on 2026-10-02.",
    "- All 17 article sources completed. Papers delivered in the September 26 edition are not repeated. The 2026-09-21 through 2026-09-27 catch-up list contains previously undelivered selections, including newly indexed articles.",
    "- Seven curated papers have unavailable abstracts. Optional Semantic Scholar enrichment was disabled; no source failures or enrichment errors were recorded in the completed collection archive.",
    "- Secondary selections include a utility-policy assessment and human social-proximity experiments. The echo-chamber catch-up paper models general biological collectives rather than directly testing human audiences.", "",
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
for key, heading in [("new_this_week", "New This Week"), ("previous_week_catch_up", "Previous Week Catch-Up"), ("late_additions", "Late Additions")]:
    grouped_section(lines, heading, kept[key])
output_path.write_text("\n".join(lines), encoding="utf-8")

audit = []
for key, items in sections.items():
    for index, item in enumerate(items):
        selected = index in selection[key]
        delivered = item.get("doi", "").lower() in previous_dois
        reason = broad_reasons.get((key, index))
        if selected and not reason:
            reason = "Substantive dedicated communication or political-science article; retained."
        elif not selected:
            reason = "Already delivered in September 26 edition." if delivered else "Outside the strict COMAP relevance threshold: natural science, clinical research, technical AI without a social-science application, or non-substantive publication noise."
        audit.append({"section": key, "index": index, "doi": item.get("doi"), "title": item["title"], "kept": selected, "reason": reason})
report = {
    "digest_date": "2026-10-03", "prepared_on": "2026-10-02", "delivery_status": "held_by_user",
    "preliminary": True, "requires_post_cutoff_collection": True,
    "windows": candidate["windows"], "candidate_counts": counts, "curated_counts": curated_counts,
    "highlights": len(highlight_indexes),
    "unavailable_abstracts": [{"section": key, "title": item["title"], "doi": item.get("doi")} for key, items in kept.items() for item in items if item.get("abstract") == "Abstract unavailable."],
    "decisions": audit,
}
(folder / "curation_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"candidate_counts": counts, "curated_counts": curated_counts, "highlights": len(highlight_indexes), "missing_abstracts": len(report["unavailable_abstracts"])}))
print(output_path)
