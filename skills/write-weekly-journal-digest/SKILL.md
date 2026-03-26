---
name: write-weekly-journal-digest
description: Write the final weekly journal digest from a candidate artifact. Use when Codex needs to read a `candidate_digest.json` file produced by the weekly-journal-digest repo, remove clearly irrelevant items that slipped through collection, and draft a polished `reviewed_digest.md` with a subject line, motivating intro, section framing, article bullets, links, and abstracts.
---

# Write Weekly Journal Digest

Read the generated `candidate_digest.json`, filter out clearly irrelevant items, preserve the remaining section boundaries, and write the final `reviewed_digest.md`.

Do not use this skill to discover articles outside the JSON or change the journal list. The skill may remove obviously irrelevant items, especially from broad science journals, but it should not invent replacements.

## Workflow

1. Open `candidate_digest.json`.
2. Read the digest key, windows, and the three sections:
   `new_this_week`, `previous_week_catch_up`, and `late_additions`.
3. Review each item for substantive fit with the project scope:
   communication, political science, or genuinely social-science-related research from the broad science journals.
4. Remove items that are plainly outside scope even if they matched a keyword mechanically.
5. Write `reviewed_digest.md` in Markdown.

## Output Contract

Write the file in this structure:

```md
Subject: Weekly journal digest for YYYY-MM-DD to YYYY-MM-DD

[Brief encouraging intro in 2-4 sentences]

## New This Week

### Journal Name
- **Article title**
  Published: YYYY-MM-DD
  Link: https://...
  Abstract: ...

## Previous Week Catch-Up

- Journal Name — Article title — https://...

## Late Additions

- Journal Name — Article title — https://...
```

## Writing Rules

- Keep the intro warm and encouraging, but do not become chatty or sentimental.
- Default to keeping items from the dedicated communication and political science journals unless they are clearly non-article noise.
- Be stricter with Nature, Science, PNAS, Science Advances, Nature Communications, Nature Human Behaviour, and Nature Machine Intelligence. Keep only items that are genuinely social-science-related.
- Good keep examples: elections, public opinion, political behavior, institutions, communication effects, media systems, survey methods, social networks, migration, inequality, policy, governance, behavioral science with clear social-science relevance.
- Good drop examples: oncology, protein structure, pure materials science, astrophysics, chemistry process engineering, cell biology, and other natural-science items with no real social-science connection.
- Preserve exact dates and links.
- Use the provided abstract text. If an abstract is `"Abstract unavailable."`, keep that wording instead of inventing a summary.
- Group the `New This Week` section by journal when there are multiple items from the same journal.
- Keep `Previous Week Catch-Up` and `Late Additions` compact unless the prompt explicitly asks for full abstracts there.
- Omit the `Late Additions` section if it is empty.
- If all sections are empty, still write a short digest with the subject line, a brief note that no qualifying articles were found, and the exact window dates.

## Guardrails

- If an item is borderline, prefer keeping it and call it out briefly rather than dropping it silently.
- Do not reorder sections.
- Do not replace links with DOI text if a URL is already provided.
- Do not add journals or articles that are not present in the JSON.
- Do not rewrite article titles.

## Handoff

Write the final answer directly as the contents of `reviewed_digest.md` unless the user asks for commentary around it.
