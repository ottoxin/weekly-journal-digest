---
name: write-weekly-journal-digest
description: Write the final weekly journal digest from a deterministic candidate artifact. Use when Codex needs to read a `candidate_digest.json` file produced by the weekly-journal-digest repo and draft a polished `reviewed_digest.md` with a subject line, motivating intro, section framing, article bullets, links, and abstracts while preserving the repo's article selection and section assignments.
---

# Write Weekly Journal Digest

Read the generated `candidate_digest.json`, preserve the selected articles and section boundaries, and write the final `reviewed_digest.md`.

Do not use this skill to discover articles, change the journal list, or re-rank the deterministic output unless the input explicitly flags an item for review.

## Workflow

1. Open `candidate_digest.json`.
2. Read the digest key, windows, and the three sections:
   `new_this_week`, `previous_week_catch_up`, and `late_additions`.
3. Preserve every selected item unless the prompt explicitly asks for editorial review.
4. Write `reviewed_digest.md` in Markdown.

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
- Preserve the deterministic article list and section placement from the input JSON.
- Preserve exact dates and links.
- Use the provided abstract text. If an abstract is `"Abstract unavailable."`, keep that wording instead of inventing a summary.
- Group the `New This Week` section by journal when there are multiple items from the same journal.
- Keep `Previous Week Catch-Up` and `Late Additions` compact unless the prompt explicitly asks for full abstracts there.
- Omit the `Late Additions` section if it is empty.
- If all sections are empty, still write a short digest with the subject line, a brief note that no qualifying articles were found, and the exact window dates.

## Guardrails

- Do not silently drop borderline items. If the prompt asks for review, call them out explicitly instead.
- Do not reorder sections.
- Do not replace links with DOI text if a URL is already provided.
- Do not add journals or articles that are not present in the JSON.
- Do not rewrite article titles.

## Handoff

Write the final answer directly as the contents of `reviewed_digest.md` unless the user asks for commentary around it.
