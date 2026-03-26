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

For the general-science group, the collector keeps only social-science-related research articles or brief reports using deterministic keyword and metadata rules.

## Weekly Windows

The Monday digest uses a rolling 28-day collection window to avoid misses from delayed indexing or transient publisher issues.

- `New This Week`: articles published during the previous 7 complete days.
- `Previous Week Catch-Up`: articles published during the 7 days before that.
- `Late Additions`: older articles that were first discovered during the current digest cycle.

This means the Monday run is not limited to “only fetch the last 7 days.” It looks back 28 days, dedupes against local state, and then classifies the output into the weekly sections above.

## Local State And Anti-Miss Strategy

- Local SQLite state lives under `.state/` by default.
- Crossref is used as the canonical metadata backbone for DOI normalization, publication dates, and abstract fallback.
- Collection is idempotent. Re-running `collect` or `build-weekly-digest` should not duplicate articles.
- Sending is idempotent per digest date and recipient unless `--force` is used.
- Collection archives are written to `.state/archives/` for debugging and auditability.

## Gmail Delivery Model

`send-digest` expects a reviewed markdown file, typically created by a Codex automation using the companion review skill.

Set these environment variables before sending:

- `WJD_GMAIL_CREDENTIALS_FILE`: Google OAuth client secret JSON path.
- `WJD_GMAIL_TOKEN_FILE`: Gmail token JSON path. If missing, the first run opens the OAuth flow and writes it.
- `WJD_GMAIL_SENDER`: Gmail address used as the sender.
- `WJD_GMAIL_RECIPIENT`: default recipient if `--recipient` is omitted.
- `WJD_CROSSREF_MAILTO`: recommended email address for polite Crossref API requests.

## CLI

Install the repo in editable mode:

```bash
python3 -m pip install -e .
```

Collect or refresh the rolling source window:

```bash
weekly-journal-digest collect
```

Build a deterministic weekly review artifact:

```bash
weekly-journal-digest build-weekly-digest --digest-date 2026-03-30 --output out/candidate_digest-2026-03-30.json
```

Send the reviewed digest:

```bash
weekly-journal-digest send-digest \
  --digest-date 2026-03-30 \
  --reviewed-digest out/reviewed_digest-2026-03-30.md
```

If the reviewed markdown starts with `Subject: ...`, that subject line is used automatically.

## Codex Skill

The companion skill is vendored in this repo at:

- `skills/write-weekly-journal-digest`

Its job is narrow: read `candidate_digest.json`, write the motivating intro and section framing, and preserve deterministic article selection unless something is explicitly flagged for review.

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
