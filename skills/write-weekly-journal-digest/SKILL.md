---
name: write-weekly-journal-digest
description: Operate the weekly COMAP Journal Bot workflow from collection through reviewed output. Use when Codex needs to determine the target week, run the weekly-journal-digest repo if needed, review the candidate set, keep all communication and political science journal articles, filter and rank general-science articles for COMAP lab interests, and produce the structured reviewed digest used for the HTML email body and attached PDF.
---

# Write Weekly Journal Digest

Read the generated `candidate_digest.json`, report the full collected set before filtering, filter out clearly irrelevant items, preserve the remaining section boundaries, and write the final `reviewed_digest.md`.

The send pipeline now uses this file in three related ways:

- The full HTML email body begins with `Special Issue Updates`, followed by `Summary`, `Highlights`, optional `Collection Snapshot`, and `Full Curated Digest` when `--full-html` is used.
- The no-send preview is generated as a sibling `.preview.html` file with `render-digest --full-html`.
- The browser-openable delivery artifact is generated as a sibling `.html` file with `send-digest`, and it is attached to the outgoing email when `--full-html` is used.
- The attached PDF begins with `Special Issue Updates`, followed by `Summary`, `Highlights`, optional `Collection Snapshot`, and `Full Curated Digest`.
- The PDF now generates a journal table of contents automatically from the journal headings in `Full Curated Digest`.

Use the bot name `COMAP Journal Bot` in the final polish and framing.

Use the companion `communication-journal-site` public special-issue export for the opening CFP section. Its CFP scope is separate from both this digest’s article list and the companion’s 70-journal article registry. Do not use this skill to discover research articles outside the candidate JSON or change the article journal list. The skill may remove obviously irrelevant items, especially from broad science journals, but it should not invent replacements.

## Workflow

1. Establish the exact digest timeframe before doing anything else.
   Use the digest date and windows from `candidate_digest.json` when they already exist.
   For the configured Saturday schedule, use Saturday as the digest date in `America/Chicago` and use Monday through Saturday of that same calendar week as `New This Week`. Collect through Saturday before production delivery. `Previous Week Catch-Up` covers the preceding Monday–Sunday. An explicitly requested historical date takes precedence.
2. Remember where the workflow left off.
   Check whether a prior run already exists under `logs/YYYY-MM-DD/`. Check `.state/digest.db` delivery records for that date before rewriting artifacts. If all intended recipients were already delivered, report the existing delivery and stop unless the user requested a refresh. Preserve sent artifacts; write an explicitly requested refreshed draft to a separate folder.
   Reuse prior candidate or reviewed artifacts only if they match the intended digest date and current journal list and filtering configuration. Recollect after changing collection keywords; old stored candidates do not include newly eligible papers.
3. Run the code to collect and build when needed.
   Use the repo CLI, not manual copying:
   `weekly-journal-digest collect --lookback-days 28 --end-date SATURDAY-YYYY-MM-DD`
   The collection end date is the Saturday digest date.
   Check the exit code and the corresponding `.state/archives/collect-*.json`: a failed source is missing coverage, not zero publications. Resolve failures before normal delivery, or clearly label partial coverage when the user has requested a partial digest. Optional enrichment warnings should be reported as metadata gaps; they do not mean the source collection failed.
   `weekly-journal-digest build-weekly-digest --digest-date SATURDAY-YYYY-MM-DD --week-start MONDAY-YYYY-MM-DD --week-end SATURDAY-YYYY-MM-DD --output logs/YYYY-MM-DD/candidate_digest-YYYY-MM-DD.json`
4. Open the candidate digest and record counts for each section and the total candidate count before manual curation. These candidates have already passed the collector’s type/title/keyword filters; do not call them every article returned by the APIs. Record raw retrieval and exclusion counts separately from the collection archive when needed.
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
   Use code to format the final email, HTML artifact, and PDF. Do not hand-design their layout inside the markdown.
8. Save the reviewed artifact and repo log.
   Integrate special issues before validation and rendering. Refresh the companion repository’s special-issue collector and public export using its CLI from `/Users/hao/NU/communication-journal-site`: `PYTHONPATH=src python3 -m communication_journal_site.cli collect-special-issues`, then `PYTHONPATH=src python3 -m communication_journal_site.cli export-public-data --output-dir data/public --flat`. This is a data refresh, not site deployment or article collection. Use that repository’s source package and persistent state. Check collection errors and export health; never equate partial coverage with no calls. Do not renew manual verification dates without checking the official source.
   Expand discovery each week with targeted web searches for official calls from Oxford/SAGE journals missing stable feeds and COMAP-relevant Nature Portfolio collections. Prioritize the current article journals, then adjacent communication/social-science titles. Open official pages and check the public-entry deadline; search snippets, publication dates, revision deadlines, and old calls are not sufficient. Record verified open calls in the companion `config/special_issue_sources.yaml` using dated manual records (review again within 10 days), then rerun its collection/export. For cross-journal calls preserve all participating journal names; use CFP-only source records without expanding article collection. Refresh existing manual records only after opening their official pages. This supplements publisher feeds; do not count it as new automated coverage.
   Back in this repo, run `weekly-journal-digest prepare-special-issues --digest-date YYYY-MM-DD --reviewed-digest logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md`. The companion location is configured as `special_issue_repo` in `config/sources.yaml`. This prepends `Special Issue Updates` and writes a sibling `.special-issues.json` source snapshot. Preserve both files and do not manually alter the generated block.
   The initial edition lists current opportunities; later editions show newly found/changed calls and deadlines within 14 days, using the last delivered snapshot. Expired/unverified calls are omitted. The next production edition includes a brief one-time announcement automatically; detailed journal lists and limitations belong in the generated `.coverage.txt` attachment, not the email introduction. Keep each call compact: title, journal/type/status, deadline, and official link. Test sends and previews do not consume it. After the first production edition succeeds, subsequent editions omit the announcement; retries of the same edition retain it. Do not hard-code an announcement date or manually remove delivery state.
   Write the structured markdown to `logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md`.
   Keep the candidate digest in the same log folder.
   Run `weekly-journal-digest render-digest --reviewed-digest logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md --full-html` to create the no-send full HTML and PDF preview files.
   Run `weekly-journal-digest send-digest --digest-date YYYY-MM-DD --reviewed-digest logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md --full-html` when sending is requested.
   Let `send-digest` generate the sibling delivery PDF and browser-openable sibling HTML in that same folder; with `--full-html`, both files are attached to the outgoing email.
   When `send-digest` runs against a reviewed digest stored under `logs/YYYY-MM-DD/`, it now auto-commits and pushes the candidate JSON, reviewed markdown, sibling PDF, sibling HTML, and special-issue source snapshot if the repo has no unrelated changes. If the repo is dirty beyond those log artifacts, it skips the git step safely.
9. Write the email summary, highlights, and final polish in the voice of `COMAP Journal Bot`.
10. Send to the configured recipient list by default.
   Use `config/recipients.json` unless the user explicitly asks for a one-off override recipient. Inspect whether `WJD_GMAIL_RECIPIENT` overrides that list before delivery. For an authorized test, resolve the named address from the recipient file and use `send-digest --test --recipient ADDRESS --full-html ...`. Test mode prefixes the subject, keeps separate delivery history, and skips git publishing. Do not use production `--force` for testing.
   Before rendering or sending, run `weekly-journal-digest validate-digest --candidate-digest CANDIDATE.json --reviewed-digest REVIEWED.md`. Fix any reported metadata, membership, or section errors. Inspect rendered HTML/PDF, not just file existence. After delivery, report the CLI’s Gmail message IDs. A Gmail API success confirms acceptance, not inbox placement.
   Preserve production send records. If a date was already sent, report that fact instead of forcing a resend. On an uncertain network send outcome, verify delivery before retrying.
   Run from the persistent repository checkout containing `.state`, credentials, and recipient configuration; a fresh worktree does not carry ignored runtime files automatically.

## Output Contract

Write the file in this structure:

```md
Subject: Weekly journal digest for YYYY-MM-DD to YYYY-MM-DD

## Special Issue Updates

[Inserted by prepare-special-issues, including the one-time coverage announcement when pending]

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

- `Special Issue Updates` appears first; `Summary` and `Highlights` follow in the email body and should remain concise and readable on a phone screen.
- The `Collection Snapshot` section is optional. If you include it, it appears in the PDF, sibling full HTML file, and `--full-html` email body.
- `Full Curated Digest` feeds the attached PDF, sibling full HTML file, and `--full-html` email body. Put the complete curated paper list there with abstracts for `New This Week`.
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
- If all sections are empty, retain Subject, Summary, Highlights, and Full Curated Digest. Put a brief no-qualifying-articles note and exact window dates in Summary; leave Highlights empty and put “No qualifying articles.” in Full Curated Digest. This still produces HTML and PDF.

## Guardrails

- If an item is borderline, prefer keeping it and call it out briefly rather than dropping it silently.
- Use the original JSON to compute the unfiltered collection counts. Do not recompute those counts from the curated sections.
- Do not reorder the major sections: `Special Issue Updates`, `Summary`, optional `Collection Snapshot`, `Highlights`, `Full Curated Digest`.
- Do not replace links with DOI text if a URL is already provided.
- Do not add research articles that are absent from the candidate JSON. Special-issue calls may come from the wider companion CFP registry; preserve their official links, deadlines, opportunity types, and coverage limitations.
- Do not rewrite article titles.
- Prefer the configured recipient list over hard-coded email addresses when finishing the send step.
- Use exact dates everywhere. Do not rely on vague references like “last week” when a specific date range can be shown.

## Handoff

For a pipeline run, report the digest date, exact windows, source failures or enrichment gaps, candidate and curated counts, artifact paths, recipients actually sent, and Gmail message IDs. Report skipped or failed sends explicitly. Return markdown contents only when the user asks for the digest text. For an audit or skill/code improvement request, report findings, changes, and verification instead of creating a production digest.
