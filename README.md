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

## Workflow

The repo is meant to be driven by an external automation, but the operational flow is simple:

1. Run `collect` to fetch journal metadata for a rolling window and upsert it into local SQLite state.
2. Run `build-weekly-digest` with the Monday digest date to generate a deterministic `candidate_digest.json`.
3. Have Codex read `candidate_digest.json` with the companion skill, filter out clearly irrelevant items, and write `reviewed_digest.md`.
4. Run `send-digest` with the reviewed markdown file to send the final email through Gmail.

The weekly window logic is:

- The collector usually runs with a 28-day lookback.
- `build-weekly-digest --digest-date YYYY-MM-DD` treats that date as the Monday handoff date.
- `New This Week` is the previous 7 complete days.
- `Previous Week Catch-Up` is the 7 days before that.
- `Late Additions` are older records that were first seen during the current cycle.

For the example week `2026-03-15` through `2026-03-21`, use `--digest-date 2026-03-22`.

## Delivery Model

`send-digest` expects a reviewed markdown file, typically created by a Codex automation using the companion review skill. It sends the final markdown through the Gmail API and records the send in local state so the same digest is not sent twice unless `--force` is used.

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

Write the reviewed digest with Codex using the vendored skill:

1. Open `out/candidate_digest-2026-03-30.json`.
2. Use `skills/write-weekly-journal-digest`.
3. Save the result as `out/reviewed_digest-2026-03-30.md`.

Send the reviewed digest:

```bash
weekly-journal-digest send-digest \
  --digest-date 2026-03-30 \
  --reviewed-digest out/reviewed_digest-2026-03-30.md
```

If the reviewed markdown starts with `Subject: ...`, that subject line is used automatically.

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

weekly-journal-digest send-digest \
  --digest-date 2026-03-22 \
  --reviewed-digest out/reviewed_digest-2026-03-22.md
```

## Codex Skill

The companion skill is vendored in this repo at:

- `skills/write-weekly-journal-digest`

Its job is narrow: read `candidate_digest.json`, remove clearly irrelevant items that slipped through collection, and write the motivating intro and section framing for the final markdown email.

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
