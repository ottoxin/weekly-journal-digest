import json
from collections import defaultdict
from pathlib import Path


root = Path(__file__).resolve().parents[2]
candidate_path = root / "logs/2026-09-12/candidate_digest-2026-09-12.json"
output_path = root / "logs/2026-09-12/reviewed_digest-2026-09-12.structured.md"
candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
new = candidate["sections"]["new_this_week"]

selected_indexes = [11, 52, 84, 92, 103, 104, 105, 112, 114, 115, 119, 131, 137, 156, 163]
highlight_indexes = [11, 52, 84, 104, 112, 114, 156, 163]

why = {
    11: "Compares how politicians in Sweden and Hungary communicate democratic resilience and decline on Facebook, directly connecting elite platform rhetoric to democratic backsliding.",
    52: "Introduces a scalable LLM-assisted system for measuring selection and framing bias across 140,000 news articles, with an explorable dataset for computational media research.",
    84: "A preregistered experiment with 2,032 participants finds that connective language can reduce reactance to disagreeable political posts, although it does not increase visible engagement.",
    104: "Real-time experiments with 48 campaign ads and roughly 28,000 participants show that emotional reactions are poor proxies for persuasion in polarized elections.",
    112: "Benchmarks 60 language models on public reason-giving and finds that plausible prose often masks weak alignment with human deliberative judgment, a key limit for AI-assisted governance.",
    114: "Links the erosion of local journalism to loneliness using state-level media data and a nationally representative survey, extending media-effects research to community belonging.",
    156: "Offers a statistically grounded method for choosing diverse sites in multi-site causal studies, helping researchers design evidence that travels beyond a single context.",
    163: "Provides causal evidence that language models use internal confidence signals when deciding whether to answer or abstain, with implications for autonomous agents and uncertainty-aware research tools.",
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


lines = [
    "Subject: Weekly journal digest for 2026-09-07 to 2026-09-12",
    "",
    "## Summary",
    "",
    "This Saturday edition covers September 7–12 and centers on democratic rhetoric, political persuasion, news bias, community information, and the use of language models in public reasoning. The strongest papers combine direct communication questions with reusable computational or research-design tools.",
    "",
    "You may have received two September 7 emails because the first was sent before that collection window closed; the second completed the same edition. Saturday delivery now aligns collection and sending, so each future email represents a distinct Monday–Saturday edition.",
    "",
    "The curated list keeps every substantive article from the dedicated communication and political science journals and eight general-science papers closely aligned with COMAP interests. Previously delivered August 31–September 6 papers are excluded from this edition to keep the reading list clean and avoid repeat content.",
    "",
    "## Collection Snapshot",
    "",
    "- Total collected candidates: 408",
    "- New This Week candidates: 164",
    "- Previous Week Catch-Up candidates: 207",
    "- Late Additions candidates: 37",
    "- Curated digest below: 15 new, 0 catch-up, 0 late additions",
    "- The candidate counts are after automatic source filters and before manual relevance review.",
    "- All 17 article sources completed successfully. Catch-up and late-addition candidates were already included in the corrected September 7 delivery and are omitted here to prevent duplicate reading.",
    "",
    "## Highlights",
    "",
]

for idx in highlight_indexes:
    item = new[idx]
    lines.extend([
        f"- **{item['title']}**",
        f"  Journal: {item['journal']}",
        f"  Published: {item['published_date']}",
        f"  Why it matters: {why[idx]}",
        f"  Link: {item['link']}",
        "",
    ])

lines.extend(["## Full Curated Digest", "", "### New This Week", ""])
by_journal = defaultdict(list)
for idx in selected_indexes:
    by_journal[new[idx]["journal"]].append(new[idx])
for journal in sorted(by_journal):
    lines.extend([f"#### {journal}", ""])
    for item in by_journal[journal]:
        lines.extend(article_lines(item))
        lines.append("")

lines.extend([
    "### Previous Week Catch-Up",
    "",
    "No catch-up papers are repeated in this edition; the corrected September 7 email already covered August 31–September 6.",
    "",
    "### Late Additions",
    "",
    "No late additions are repeated in this edition; relevant late-indexed papers were included in the corrected September 7 email.",
    "",
])

output_path.write_text("\n".join(lines), encoding="utf-8")
print(output_path)
