"""Import the companion monitor's public CFP snapshot and track delivered updates."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

HEADING = "## Special Issue Updates"
NOTICE_KEY = "special-issues-introduction-v1"


def eligible_calls(repo: Path, as_of: date) -> tuple[list[dict], dict]:
    public = repo / "data/public"
    health = json.loads((public / "health.json").read_text())
    run = json.loads((public / "special_issue_collection.json").read_text())
    synced = datetime.fromisoformat(run["run_started_at"]).date()
    if (as_of - synced).days > 10 or synced > as_of:
        raise ValueError("Special-issue snapshot is stale or dated after the digest; refresh the companion collector first.")
    rows = [json.loads(line) for line in (public / "special_issues.jsonl").read_text().splitlines() if line.strip()]
    configured = yaml.safe_load((repo / "config/special_issue_sources.yaml").read_text())["sources"]
    manual = {s["id"]: s for s in configured if s.get("source_type") == "manual"}
    stale_manual = set()
    calls = {}
    for row in rows:
        if row["status"] not in {"active", "upcoming"}:
            continue
        if row.get("deadline") and date.fromisoformat(row["deadline"]) < as_of:
            continue
        source = manual.get(row.get("source_id"))
        if source:
            verified = source.get("verified_on")
            if not verified or not 0 <= (as_of - date.fromisoformat(str(verified))).days <= 10:
                stale_manual.add(row.get("journal", row["source_id"]))
                continue
        if row["status"] not in {"active", "upcoming"}:
            continue
        if row.get("deadline") and date.fromisoformat(row["deadline"]) < as_of:
            continue
        if not row.get("source_url", "").startswith("https://"):
            continue
        calls[row["source_url"]] = row
    return sorted(calls.values(), key=lambda r: (r.get("deadline") or "9999", r["journal"], r["title"])), {"health": health, "run": run, "stale_manual": sorted(stale_manual)}


def coverage_details(repo: Path, article_sources: list) -> str:
    journals = json.loads((repo / "data/public/journals.json").read_text())
    names = {j["id"]: j["title"] for j in journals if j.get("active", True)}
    health = json.loads((repo / "data/public/health.json").read_text())
    automated = set(health["special_issue_run"]["automated_publisher_journal_ids"])
    sources = yaml.safe_load((repo / "config/special_issue_sources.yaml").read_text())["sources"]
    manual = {s["journal_id"] for s in sources if s.get("active", True) and s["source_type"] == "manual"}
    manual_names = sorted({names.get(s["journal_id"], s["label"]) for s in sources if s.get("active", True) and s["source_type"] == "manual"})
    remaining = sorted(names[key] for key in names.keys() - automated - manual)
    article_names = {source.journal for source in article_sources}
    article_automated = sorted(article_names & {names[key] for key in automated})
    article_outside = sorted(article_names - set(names.values()))
    return "\n\n".join([
        "Special-issue coverage announcement (for this edition only): Future COMAP Journal Bot digests will include special-issue and call-for-papers updates at the front, beginning with this edition. We will flag newly found or changed calls and approaching public-entry deadlines, with official source links.",
        f"Our regular article digest currently collects these {len(article_sources)} journals: " + "; ".join(s.journal for s in article_sources) + ". The broad-science titles are filtered for social-science relevance; the companion site's wider article registry is not being added to this article digest.",
        "Within the regular article list, automated CFP monitoring covers: " + ("; ".join(article_automated) or "none") + ". These article-digest journals are outside the companion article registry, although individually verified calls can still be included: " + ("; ".join(article_outside) or "none") + ". Article coverage and special-issue coverage are separate.",
        f"Special-issue monitoring has automated publisher coverage for {len(automated)} journals: " + "; ".join(sorted(names[key] for key in automated)) + ". This combines the Taylor & Francis special-issues API and Media and Communication's thematic-issue listing; Journal of Public Relations Research also has a supplemental direct page.",
        "Additional dated manual records/proposal routes cover: " + "; ".join(manual_names) + ". These require renewed verification and are not complete automated journal feeds. Communication and the Public is an additional proposal source outside the site's 70-journal article registry.",
        "Journals in the companion registry without systematic automated CFP coverage or a configured manual call/proposal record: " + "; ".join(remaining) + ". Some receive dated official-page audits, but those audits are not continuous CFP feeds. Oxford, SAGE, Elsevier, Wiley, and Hogrefe are not covered publisher-wide. The NCA page supplies discovery only.",
        "The 70-journal registry does not imply complete special-issue coverage. Journals outside the configured sources, calls available only through email/social media or inaccessible pages, expired calls, and invitation-only manuscript stages are outside systematic coverage. Unknown deadlines are labeled; proposal routes are distinguished from paper submissions."
    ])


def coverage_announcement(repo: Path, article_sources: list) -> str:
    health = json.loads((repo / "data/public/health.json").read_text())
    count = len(health["special_issue_run"]["automated_publisher_journal_ids"])
    return (
        "Starting this week, special-issue calls and approaching deadlines will lead the digest. "
        f"We monitor {count} journals through publisher feeds and add individually verified calls from other journals. "
        f"Our regular {len(article_sources)}-journal article digest continues as before. "
        "Coverage varies by journal; the attached coverage note lists the journals and sources."
    )


def render_updates(calls: list[dict], previous: list[dict] | None, as_of: date, status: dict, announcement: str = "") -> str:
    old = {row["source_url"]: row for row in previous or []}
    lines = [HEADING, ""]
    if announcement:
        lines += [announcement, ""]
    run = status["run"]
    lines += [f"Calls checked: {as_of.isoformat()}.", ""]
    if status.get("stale_manual"):
        lines += ["Manual calls omitted pending renewed official-page verification: " + "; ".join(status["stale_manual"]) + ".", ""]
    if run.get("errors"):
        lines += ["Coverage warning: some sources failed; retained calls are last-known findings, not newly verified results. Failed sources: " + "; ".join(str(e.get("source_id", "unknown")) for e in run["errors"]) + ".", ""]
    if status["health"].get("special_issue_status") not in {None, "current"}:
        lines += ["Coverage warning: the companion monitor reports reduced or stale special-issue coverage. Check official pages before relying on deadlines.", ""]
    emitted = 0
    for call in calls:
        prior = old.get(call["source_url"])
        if previous is None:
            change = "Current opportunity (initial inventory)"
        elif prior is None:
            change = "Newly found"
        elif any(prior.get(k) != call.get(k) for k in ["title", "deadline", "status", "opportunity_type", "snippet"]):
            change = "Updated"
        elif call.get("deadline") and date.fromisoformat(call["deadline"]) <= as_of + timedelta(days=14):
            change = "Deadline within 14 days"
        else:
            continue
        emitted += 1
        label = "Opens later" if call["status"] == "upcoming" else "Open"
        if previous is not None:
            label = change
        kind = call.get("opportunity_type", "call-for-papers").replace("-", " ")
        lines += [f"- **{call['title']}**", f"  {call['journal']} | {label} | {kind}", f"  Deadline: {call.get('deadline') or 'Not specified; see official call'}", f"  Link: {call['source_url']}", ""]
    if not emitted:
        lines += ["No new or changed eligible calls or deadlines within 14 days in the available snapshot.", ""]
    return "\n".join(lines).strip()


def extract_block(markdown: str) -> str:
    if HEADING not in markdown.splitlines():
        return ""
    after = markdown.split(HEADING, 1)[1]
    return (HEADING + after.split("\n## ", 1)[0]).strip()


def prepare_updates(repo: Path, reviewed_path: Path, store, digest_key: str, article_sources: list, as_of: date | None = None) -> Path:
    as_of = as_of or date.fromisoformat(digest_key)
    calls, status = eligible_calls(repo, as_of)
    previous = store.last_special_issue_snapshot(before_digest=digest_key)
    announcement = coverage_announcement(repo, article_sources) if store.announcement_pending(NOTICE_KEY, digest_key) else ""
    block = render_updates(calls, previous, as_of, status, announcement)
    markdown = reviewed_path.read_text()
    existing = extract_block(markdown)
    if existing:
        markdown = markdown.replace(existing, "", 1)
    subject, separator, body = markdown.partition("\n")
    if not subject.startswith("Subject:"):
        raise ValueError("Reviewed digest must start with Subject:.")
    reviewed_path.write_text(subject + "\n\n" + block + "\n\n" + body.lstrip())
    sidecar = reviewed_path.with_suffix(".special-issues.json")
    sidecar.write_text(json.dumps({"digest_key": digest_key, "source_repo": str(repo.resolve()), "calls": calls, "status": status, "announcement_key": NOTICE_KEY if announcement else None, "coverage_text": coverage_details(repo, article_sources) if announcement else "", "markdown": block}, indent=2))
    if announcement:
        reviewed_path.with_suffix(".coverage.txt").write_text(coverage_details(repo, article_sources))
    return sidecar


def delivery_metadata(reviewed_path: Path, markdown: str, digest_key: str) -> dict | None:
    block = extract_block(markdown)
    if not block:
        return None
    sidecar = reviewed_path.with_suffix(".special-issues.json")
    if not sidecar.exists():
        raise ValueError("Special-issue section requires its prepared .special-issues.json source snapshot.")
    payload = json.loads(sidecar.read_text())
    if payload["digest_key"] != digest_key or payload["markdown"] != block:
        raise ValueError("Special-issue snapshot date/content mismatch; rerun prepare-special-issues.")
    return payload
