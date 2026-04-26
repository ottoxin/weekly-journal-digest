---
name: write-weekly-journal-digest
description: Operate the weekly COMAP Journal Bot workflow from collection through reviewed output. Use when Codex needs to determine the target week, run the weekly-journal-digest repo if needed, review the candidate set, keep all communication and political science journal articles, filter and rank general-science articles for COMAP lab interests, and produce the structured reviewed digest used for the HTML email body and attached PDF.
---

# Write Weekly Journal Digest

Read the generated `candidate_digest.json`, report the full collected set before filtering, filter out clearly irrelevant items, preserve the remaining section boundaries, and write the final `reviewed_digest.md`.

The send pipeline now uses this file in two different ways:

- The email body is built from the short `Summary` and `Highlights` sections.
- The attached PDF is built from the `Summary`, optional `Collection Snapshot`, and `Full Curated Digest` sections.
- The PDF now generates a journal table of contents automatically from the journal headings in `Full Curated Digest`.

Use the bot name `COMAP Journal Bot` in the final polish and framing.

Do not use this skill to discover articles outside the JSON or change the journal list. The skill may remove obviously irrelevant items, especially from broad science journals, but it should not invent replacements.

## Workflow

1. Establish the exact digest timeframe before doing anything else.
   Use the digest date and windows from `candidate_digest.json` when they already exist.
   If the digest artifact is missing or stale, compute the Monday digest date first and use the previous complete 7-day week as `New This Week`.
2. Remember where the workflow left off.
   Check whether a prior run already exists under `logs/YYYY-MM-DD/`.
   Reuse prior candidate or reviewed artifacts only if they match the intended digest date and current journal list.
3. Run the code to collect and build when needed.
   Use the repo CLI, not manual copying:
   `weekly-journal-digest collect --lookback-days 28 --end-date YYYY-MM-DD`
   `weekly-journal-digest build-weekly-digest --digest-date YYYY-MM-DD --output logs/YYYY-MM-DD/candidate_digest-YYYY-MM-DD.json`
4. Open the candidate digest and record the original unfiltered counts for each section and the total candidate count.
5. Review and organize the articles.
   Keep all substantive articles from the dedicated communication and political science journals unless they are clearly non-article noise.
   Filter the broad general-science journals much more aggressively.
6. Rank the broad general-science articles using COMAP lab interests.
   Highest priority:
   authoritarian information control in the digital age, censorship, propaganda, repression, platform manipulation, algorithmic governance, state-media strategy, and digital authoritarianism.
   multimodal political communication, including images, video, audio, memes, political visuals, campaign media, creator politics, and audience response to multimodal content.
   AI for computational social science, including large language models, multimodal models, automated measurement, annotation, classification, validation, research methods, and computational social-science infrastructure.
   Secondary priority:
   misinformation, public opinion, elections, political behavior, institutions, democracy, inequality, migration, collective action, governance, and policy.
   Low priority and usually drop:
   biomedical, clinical, chemistry, materials, pure neuroscience, astrophysics, and other natural-science papers with no strong COMAP-relevant social-science connection.
7. Build the final curated article list.
   The reviewed artifact should contain all kept articles.
   Use code to format the final email and PDF. Do not hand-design their layout inside the markdown.
8. Save the reviewed artifact and repo log.
   Write the structured markdown to `logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md`.
   Keep the candidate digest in the same log folder.
   Run `weekly-journal-digest render-digest --reviewed-digest logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md` when the user wants a no-send preview of the email and PDF.
   Let `send-digest` generate the sibling delivery PDF in that same folder when sending is requested.
   When `send-digest` runs against a reviewed digest stored under `logs/YYYY-MM-DD/`, it now auto-commits and pushes the candidate JSON, reviewed markdown, and sibling PDF if the repo has no unrelated changes. If the repo is dirty beyond those log artifacts, it skips the git step safely.
9. Write the email summary, highlights, and final polish in the voice of `COMAP Journal Bot`.
10. Send to the configured recipient list by default.
   Use `config/recipients.json` unless the user explicitly asks for a one-off override recipient.

## Output Contract

Write the file in this structure:

```md
Subject: Weekly journal digest for YYYY-MM-DD to YYYY-MM-DD

## Summary

[Brief encouraging overview in 1-2 paragraphs, optionally followed by 2-4 bullet points]

## Collection Snapshot

- Total collected candidates: N
- New This Week candidates: N
- Previous Week Catch-Up candidates: N
- Late Additions candidates: N
- Curated digest below: N new, N catch-up, N late additions
- Note: The full collected set above is before manual relevance filtering, while the attached PDF reflects the curated digest.

## Highlights

- **Article title**
  Journal: Journal Name
  Published: YYYY-MM-DD
  Why it matters: One or two sentences explaining why this paper is especially worth opening this week.
  Link: https://...

## Full Curated Digest

### New This Week

#### Journal Name
- **Article title**
  Published: YYYY-MM-DD
  Authors: Author One; Author Two
  Affiliations: Affiliation One; Affiliation Two
  DOI: 10.xxxx/xxxxx
  Link: https://...
  Abstract: ...

### Previous Week Catch-Up

#### Journal Name
- **Article title**
  Published: YYYY-MM-DD
  Authors: Author One; Author Two
  Affiliations: Affiliation One; Affiliation Two
  DOI: 10.xxxx/xxxxx
  Link: https://...
  Abstract: ...

### Late Additions

#### Journal Name
- **Article title**
  Published: YYYY-MM-DD
  Authors: Author One; Author Two
  Affiliations: Affiliation One; Affiliation Two
  DOI: 10.xxxx/xxxxx
  Link: https://...
  Abstract: ...
```

## Writing Rules

- `Summary` and `Highlights` are the only parts that appear in the main email body. Keep them concise and readable on a phone screen.
- The `Collection Snapshot` section is optional. If you include it, it will only appear in the PDF, not the email body.
- `Full Curated Digest` is for the attached PDF. Put the complete curated paper list there with abstracts for `New This Week`.
- Write the `Summary` in a more vivid, human, academically polished voice. It should sound like a thoughtful weekly brief, not a system notification.
- The `Summary` may mix short paragraphs and bullet points. Bullet points are encouraged when they make the week easier to scan quickly.
- For every kept article in `Full Curated Digest`, include abstract, authors, affiliations when available, DOI, and link.
- If affiliations are unavailable, omit the `Affiliations:` line rather than inventing one.
- If DOI is unavailable, keep the `Link:` line and omit the `DOI:` line.
- Assume the reader cares most about computational media, political communication, authoritarian information control, multimodal political communication, and AI for computational social science.
- Keep the intro warm and encouraging, but do not become chatty or sentimental.
- If you include a collection snapshot, explicitly state that the counts reflect the complete collected set before manual relevance filtering.
- Include 5 to 8 highlights unless the curated set is smaller than that. Prefer highlights from `New This Week`, but you may include an unusually important catch-up or late addition.
- Each `Why it matters` note should be specific and short. Do not repeat the abstract.
- Default to keeping items from the dedicated communication and political science journals unless they are clearly non-article noise.
- Be stricter with Nature, Science, PNAS, Science Advances, Nature Communications, Nature Human Behaviour, Nature Machine Intelligence, and Nature Computational Science. Keep only items that are genuinely social-science-related.
- Good keep examples: elections, public opinion, political behavior, institutions, communication effects, media systems, survey methods, social networks, migration, inequality, policy, governance, behavioral science with clear social-science relevance.
- Good drop examples: oncology, protein structure, pure materials science, astrophysics, chemistry process engineering, cell biology, and other natural-science items with no real social-science connection.
- Do not hide the size of the original collection. The email should make clear how many papers were gathered before filtering and that the sections below are curated from that larger set.
- Preserve exact dates and links.
- Use the provided abstract text. If an abstract is `"Abstract unavailable."`, keep that wording instead of inventing a summary.
- Do not add a manual table of contents block to the markdown. The code generates the PDF journal table of contents automatically from the journal headings.
- Group the `New This Week` section by journal when there are multiple items from the same journal.
- `Previous Week Catch-Up` and `Late Additions` should also include article-level metadata lines now. They can still be shorter than `New This Week`, but do not drop abstract, authors, affiliations, or DOI when available.
- Omit the `Late Additions` section if it is empty.
- If all sections are empty, still write a short digest with the subject line, a brief note that no qualifying articles were found, and the exact window dates.

## Guardrails

- If an item is borderline, prefer keeping it and call it out briefly rather than dropping it silently.
- Use the original JSON to compute the unfiltered collection counts. Do not recompute those counts from the curated sections.
- Do not reorder the major sections: `Summary`, optional `Collection Snapshot`, `Highlights`, `Full Curated Digest`.
- Do not replace links with DOI text if a URL is already provided.
- Do not add journals or articles that are not present in the JSON.
- Do not rewrite article titles.
- Prefer the configured recipient list over hard-coded email addresses when finishing the send step.
- Use exact dates everywhere. Do not rely on vague references like “last week” when a specific date range can be shown.

## Handoff

Write the final answer directly as the contents of `reviewed_digest.md` unless the user asks for commentary around it.
