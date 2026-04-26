# Weekly Journal Digest

`weekly-journal-digest` is a local Python repo for collecting weekly journal articles, reconciling them against Crossref, generating a deterministic `candidate_digest.json`, and sending a reviewed digest through the Gmail API.

Scheduling is intentionally **not** implemented in this repo. Codex automations are expected to run the CLI on Mondays.

## Journal List

Communication journals:

- Journal of Communication
- Journal of Computer-Mediated Communication
- Political Communication
- Human Communication Research
- Communication Research
- Communication Methods and Measures

Political science journals:

- American Journal of Political Science
- American Political Science Review
- Political Analysis

General science journals with social-science filtering:

- Nature
- Science
- PNAS
- Science Advances
- Nature Human Behaviour
- Nature Communications
- Nature Machine Intelligence
- Nature Computational Science

For the general-science group, the collector keeps only social-science-related research articles or brief reports using deterministic keyword and metadata rules.

## Weekly Windows

The Monday digest uses a rolling 28-day collection window to avoid misses from delayed indexing or transient publisher issues.

- `New This Week`: articles published during the previous 7 complete days.
- `Previous Week Catch-Up`: articles published during the 7 days before that.
- `Late Additions`: older articles that were first discovered during the current digest cycle.

This means the Monday run is not limited to “only fetch the last 7 days.” It looks back 28 days, dedupes against local state, and then classifies the output into the weekly sections above.

## Local State And Anti-Miss Strategy

- Local SQLite state lives under `.state/` by default.
- Recipient configuration lives in `config/recipients.json` by default.
- Crossref is used as the canonical metadata backbone for DOI normalization, publication dates, and abstract fallback.
- Collection now uses a layered metadata approach:
  Crossref for discovery, optional Semantic Scholar DOI enrichment for abstracts and citation counts, and OpenAlex DOI fallback for abstracts that remain missing.
- Collection is idempotent. Re-running `collect` or `build-weekly-digest` should not duplicate articles.
- Collection automatically retries transient DNS and transport failures before marking a source as failed.
- Sending is idempotent per digest date and recipient unless `--force` is used.
- Collection archives are written to `.state/archives/` for debugging and auditability.

## Workflow

The repo is meant to be driven by an external automation, but the operational flow is simple:

1. Determine the Monday digest date and the exact weekly window.
2. Run `collect` to fetch journal metadata for a rolling window and upsert it into local SQLite state.
3. Run `build-weekly-digest` with the Monday digest date to generate a deterministic `candidate_digest.json`.
4. Have Codex read `candidate_digest.json` with the companion skill, keep all communication and political science journal articles, filter and rank the general-science candidates for COMAP relevance, and write a structured `reviewed_digest.md`.
   For every kept article in the full curated digest, include abstract, authors, affiliations when available, DOI, and link.
5. Run `render-digest` with the reviewed markdown file to generate no-send preview artifacts: a plain-text body, HTML email body, and PDF.
   Inspect the `.preview.html` and `.preview.pdf` files before delivery.
6. Run `send-digest` with the reviewed markdown file to send a short HTML summary email and attach the full curated digest as a PDF.
   The email body uses `Summary` and `Highlights`; the PDF includes the full curated digest and an automatically generated journal table of contents.
   By default it sends to the active emails in `config/recipients.json`. Use `--recipient` only for a one-off override.
7. Save the markdown and PDF under a repo log folder if you want the run preserved in GitHub history.
   When `send-digest` is run against a reviewed digest stored under `logs/YYYY-MM-DD/`, it now auto-commits and pushes the candidate JSON, reviewed markdown, and sibling PDF if the repo has no unrelated changes. If the repo is otherwise dirty, it skips the git step safely.

The weekly window logic is:

- The collector usually runs with a 28-day lookback.
- `build-weekly-digest --digest-date YYYY-MM-DD` treats that date as the Monday handoff date.
- `New This Week` is the previous 7 complete days.
- `Previous Week Catch-Up` is the 7 days before that.
- `Late Additions` are older records that were first seen during the current cycle.

For the example week `2026-03-15` through `2026-03-21`, use `--digest-date 2026-03-22`.

## Run Logs

For repeatable automation runs, keep artifacts in a tracked log folder inside the repo:

- `logs/YYYY-MM-DD/candidate_digest-YYYY-MM-DD.json`
- `logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.md`
- `logs/YYYY-MM-DD/reviewed_digest-YYYY-MM-DD.structured.pdf`

The companion skill now assumes this layout so the reviewed markdown and generated PDF can be committed to GitHub as an execution log when desired.
If `send-digest` is pointed at the reviewed markdown inside one of these log folders, the CLI will now try to commit and push those log artifacts automatically when the repo is otherwise clean.

## Recipients

The default recipient list is stored in:

- `config/recipients.json`

Example:

```json
{
  "recipients": [
    {
      "email": "haohangxin@u.northwestern.edu",
      "name": "Otto",
      "active": true
    }
  ]
}
```

`send-digest` sends to every active address in that file unless `--recipient` is provided.

## Delivery Model

`send-digest` expects a reviewed markdown file, typically created by a Codex automation using the companion review skill.

- Use `render-digest` first when you want to inspect the email and PDF without opening Gmail, writing send records, or auto-committing log artifacts.
- If the reviewed file follows the current structured format, the repo sends a short HTML email built from `Summary` and `Highlights`, and attaches a PDF built from `Summary`, the optional `Collection Snapshot`, and `Full Curated Digest`.
- If the reviewed file uses the older unstructured format, the repo falls back to the legacy plain-text send path.
- Sends are still recorded in local state so the same digest is not sent twice unless `--force` is used.

## CLI

Install the repo in editable mode:

```bash
python3 -m pip install -e .
```

Collect or refresh the rolling source window:

```bash
weekly-journal-digest collect
```

Optional enrichment environment:

```bash
export WJD_SEMANTIC_SCHOLAR_API_KEY=your_key_here
```

If the key is not set, the collector still runs and uses OpenAlex fallback for missing abstracts.

Build a deterministic weekly review artifact:

```bash
weekly-journal-digest build-weekly-digest --digest-date 2026-03-30 --output out/candidate_digest-2026-03-30.json
```

Write the reviewed digest with Codex using the vendored skill:

1. Open `out/candidate_digest-2026-03-30.json`.
2. Use `skills/write-weekly-journal-digest`.
3. Save the result as `out/reviewed_digest-2026-03-30.md`.

The reviewed markdown should now contain these major sections:

1. `Summary`
2. optional `Collection Snapshot`
3. `Highlights`
4. `Full Curated Digest`

For a logged run, save the reviewed markdown in `logs/YYYY-MM-DD/` instead of `out/`.

Render no-send previews:

```bash
weekly-journal-digest render-digest \
  --reviewed-digest out/reviewed_digest-2026-03-30.md \
  --recipient-name "Haohang Xin"
```

This writes sibling preview files using the reviewed digest stem:

- `reviewed_digest-2026-03-30.preview.txt`
- `reviewed_digest-2026-03-30.preview.html`
- `reviewed_digest-2026-03-30.preview.pdf`

Send the reviewed digest:

```bash
weekly-journal-digest send-digest \
  --digest-date 2026-03-30 \
  --reviewed-digest out/reviewed_digest-2026-03-30.md
```

Optional one-off override:

```bash
weekly-journal-digest send-digest \
  --digest-date 2026-03-30 \
  --reviewed-digest out/reviewed_digest-2026-03-30.md \
  --recipient someone@example.com
```

If the reviewed markdown starts with `Subject: ...`, that subject line is used automatically.

When the reviewed file follows the current skill contract, `send-digest` also writes a sibling PDF file next to the reviewed markdown before attaching it to the outgoing email. That PDF includes a generated table of contents linking to the journal sections in the curated digest.
If that reviewed markdown lives under `logs/YYYY-MM-DD/`, `send-digest` will also try to git add, commit, and push the candidate JSON, reviewed markdown, and generated PDF after a successful send, but only when the repo has no unrelated changes.

## Example Weekly Run

```bash
python3 -m pip install -e .

weekly-journal-digest collect \
  --lookback-days 28 \
  --end-date 2026-03-22

weekly-journal-digest build-weekly-digest \
  --digest-date 2026-03-22 \
  --output out/candidate_digest-2026-03-22.json

# Codex reads the candidate JSON and writes:
# out/reviewed_digest-2026-03-22.md

weekly-journal-digest render-digest \
  --reviewed-digest out/reviewed_digest-2026-03-22.md

weekly-journal-digest send-digest \
  --digest-date 2026-03-22 \
  --reviewed-digest out/reviewed_digest-2026-03-22.md
```

## Codex Skill

The companion skill is vendored in this repo at:

- `skills/write-weekly-journal-digest`

Its job is narrow: determine the target week, run the repo when needed, keep all communication and political science journal articles, filter and rank the general-science candidates for COMAP priorities, write a more human but still academic `Summary`, pick the limited set of in-email highlights, and produce the full curated digest used for the attached PDF.

Because the detailed workflow lives in the skill, the Codex automation prompt can stay short. A sufficient prompt is:

```text
Use the [$write-weekly-journal-digest](/Users/hao/.codex/skills/write-weekly-journal-digest/SKILL.md) skill and run the weekly COMAP Journal Bot pipeline in /Users/hao/NU/weekly-journal-digest.
```

The ranking emphasis for broad general-science papers is:

- Authoritarian information control in the digital age
- Multimodal political communication
- AI for computational social science

If you want Codex to auto-discover it locally, copy or sync the folder to:

- `/Users/hao/.codex/skills/write-weekly-journal-digest`

## Repo Layout

```text
config/sources.yaml          Source registry and journal list
skills/write-weekly-journal-digest/
src/weekly_journal_digest/   Python package
tests/                       Unit, integration, and end-to-end tests
examples/                    Example reviewed digest format
```

## Tests

Run the test suite with:

```bash
python3 -m unittest discover -s tests -v
```
