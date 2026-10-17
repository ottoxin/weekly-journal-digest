from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .adapters import build_adapter_registry
from .config import load_config
from .digest import build_candidate_digest, compute_weekly_windows
from .emailing import EmailAttachment, GmailSender, describe_delivery_error, extract_subject
from .enrichment import build_metadata_enricher
from .filters import should_include_record
from .reviewed_digest import (
    DELIVERY_PREFERENCES_TEXT,
    parse_reviewed_digest,
    render_curated_digest_pdf,
    render_full_digest_html,
    render_summary_html,
    render_summary_plain_text,
)
from .storage import StateStore
from .validation import validate_reviewed_digest
from .special_issues import prepare_updates, delivery_metadata


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "sources.yaml"


@dataclass(frozen=True, slots=True)
class Recipient:
    email: str
    name: str | None = None

    @property
    def salutation_name(self) -> str:
        cleaned = " ".join((self.name or "").split())
        if cleaned:
            return cleaned
        local_part = self.email.split("@", 1)[0]
        inferred = " ".join(
            piece for piece in re_split_recipient_name(local_part) if piece
        )
        return inferred.title() if inferred else "Reader"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    load_local_env(getattr(args, "config", None))
    return args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Weekly journal digest CLI")
    subparsers = parser.add_subparsers(dest="command")

    collect_parser = subparsers.add_parser("collect", help="Collect article metadata into local state.")
    collect_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    collect_parser.add_argument("--state-dir", default=None)
    collect_parser.add_argument("--lookback-days", type=int, default=None)
    collect_parser.add_argument("--end-date", default=None, help="Collection end date in YYYY-MM-DD.")
    collect_parser.set_defaults(func=cmd_collect)

    build_parser_ = subparsers.add_parser(
        "build-weekly-digest",
        help="Build candidate_digest.json for editorial review.",
    )
    build_parser_.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    build_parser_.add_argument("--state-dir", default=None)
    build_parser_.add_argument("--digest-date", default=None, help="Digest date in YYYY-MM-DD.")
    build_parser_.add_argument("--week-start", default=None, help="Override New This Week start date.")
    build_parser_.add_argument("--week-end", default=None, help="Override New This Week end date.")
    build_parser_.add_argument("--output", default=None)
    build_parser_.set_defaults(func=cmd_build_weekly_digest)

    validate_parser = subparsers.add_parser("validate-digest", help="Check reviewed articles against candidate JSON.")
    validate_parser.add_argument("--candidate-digest", required=True)
    validate_parser.add_argument("--reviewed-digest", required=True)
    validate_parser.set_defaults(func=cmd_validate_digest)

    special_parser = subparsers.add_parser("prepare-special-issues", help="Prepend companion CFP updates and the pending one-time coverage announcement.")
    special_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    special_parser.add_argument("--state-dir", default=None)
    special_parser.add_argument("--source-repo", default=None)
    special_parser.add_argument("--digest-date", required=True)
    special_parser.add_argument("--as-of", default=None, help="CFP check date for a refreshed edition; defaults to digest date.")
    special_parser.add_argument("--reviewed-digest", required=True)
    special_parser.set_defaults(func=cmd_prepare_special_issues)

    render_parser = subparsers.add_parser(
        "render-digest",
        help="Render email and PDF preview artifacts without sending.",
    )
    render_parser.add_argument("--reviewed-digest", required=True)
    render_parser.add_argument("--output-dir", default=None)
    render_parser.add_argument("--recipient-name", default=None)
    render_parser.add_argument(
        "--full-html",
        action="store_true",
        help="Include the collection snapshot and full curated digest in the HTML preview body.",
    )
    render_parser.set_defaults(func=cmd_render_digest)

    send_parser = subparsers.add_parser("send-digest", help="Send the reviewed digest via Gmail API.")
    send_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    send_parser.add_argument("--state-dir", default=None)
    send_parser.add_argument("--digest-date", default=None, help="Digest date in YYYY-MM-DD.")
    send_parser.add_argument("--reviewed-digest", required=True)
    send_parser.add_argument("--recipient", default=None)
    send_parser.add_argument("--subject", default=None)
    send_parser.add_argument("--force", action="store_true")
    send_parser.add_argument(
        "--test", action="store_true",
        help="Send only to an explicit --recipient, label TEST, and isolate delivery history; skip git publishing.",
    )
    send_parser.add_argument(
        "--full-html",
        action="store_true",
        help="Include the collection snapshot and full curated digest in the outgoing HTML body.",
    )
    send_parser.set_defaults(func=cmd_send_digest)

    return parser


def cmd_collect(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    state_dir = resolve_state_dir(args.config, args.state_dir or config.state_dir)
    store = StateStore(state_dir / "digest.db")
    adapters = build_adapter_registry(mailto=os.environ.get("WJD_CROSSREF_MAILTO"))
    enricher = build_metadata_enricher(
        semantic_scholar_api_key=os.environ.get("WJD_SEMANTIC_SCHOLAR_API_KEY")
    )
    end_date = parse_date(args.end_date) if args.end_date else date.today()
    lookback_days = args.lookback_days if args.lookback_days is not None else config.default_lookback_days
    if lookback_days < 1:
        raise ValueError("--lookback-days must be positive.")
    start_date = end_date - timedelta(days=lookback_days - 1)
    seen_at = utc_now().isoformat()
    archive_dir = state_dir / "archives"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_payload = {
        "run_started_at": seen_at,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "sources": [],
    }
    stored_total = 0
    errors = []
    for source in config.sources:
        try:
            adapter = adapters[source.adapter]
            records = adapter.collect(source, start_date, end_date)
            enrichment_error = None
            try:
                records = enricher.enrich_records(records)
            except Exception as exc:
                enrichment_error = str(exc)
                print(f"Optional enrichment failed for {source.id}; retaining source metadata: {exc}", file=sys.stderr)
            included = []
            excluded_reasons: dict[str, int] = {}
            for record in records:
                include, reason = should_include_record(source, record, config.social_science_keywords)
                if include:
                    record.relevance_status = reason
                    included.append(record)
                else:
                    excluded_reasons[reason] = excluded_reasons.get(reason, 0) + 1
            store.upsert_articles(included, seen_at=seen_at)
            stored_total += len(included)
            archive_payload["sources"].append(
                {
                    "source_id": source.id,
                    "journal": source.journal,
                    "retrieved": len(records),
                    "stored": len(included),
                    "excluded_reasons": excluded_reasons,
                    "enrichment_error": enrichment_error,
                }
            )
        except Exception as exc:  # pragma: no cover - exercised through CLI behavior
            errors.append({"source_id": source.id, "error": str(exc)})
            archive_payload["sources"].append(
                {
                    "source_id": source.id,
                    "journal": source.journal,
                    "retrieved": 0,
                    "stored": 0,
                    "error": str(exc),
                }
            )
    archive_path = archive_dir / f"collect-{seen_at.replace(':', '-')}.json"
    archive_path.write_text(json.dumps(archive_payload, indent=2), encoding="utf-8")
    print(
        f"Collected {stored_total} articles from {len(config.sources)} sources "
        f"for {start_date.isoformat()} to {end_date.isoformat()}."
    )
    if errors:
        print(f"{len(errors)} source(s) failed. See {archive_path}.", file=sys.stderr)
        return 1
    return 0


def cmd_build_weekly_digest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    state_dir = resolve_state_dir(args.config, args.state_dir or config.state_dir)
    store = StateStore(state_dir / "digest.db")
    digest_date = parse_date(args.digest_date) if args.digest_date else date.today()
    output_path = Path(args.output) if args.output else REPO_ROOT / "out" / f"candidate_digest-{digest_date.isoformat()}.json"
    week_start = parse_date(args.week_start) if args.week_start else None
    week_end = parse_date(args.week_end) if args.week_end else None
    if bool(week_start) != bool(week_end):
        raise ValueError("--week-start and --week-end must be supplied together.")
    payload = build_candidate_digest(
        store, config, digest_date, output_path, new_start=week_start, new_end=week_end
    )
    print(
        f"Wrote candidate digest to {output_path} "
        f"({len(payload['sections']['new_this_week'])} new / "
        f"{len(payload['sections']['previous_week_catch_up'])} catch-up / "
        f"{len(payload['sections']['late_additions'])} late additions)."
    )
    return 0


def cmd_prepare_special_issues(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    source_repo = args.source_repo or config.special_issue_repo
    if not source_repo:
        raise ValueError("Configure special_issue_repo or pass --source-repo.")
    store = StateStore(resolve_state_dir(args.config, args.state_dir or config.state_dir) / "digest.db")
    path = prepare_updates(resolve_repo_path(args.config, source_repo), Path(args.reviewed_digest), store, args.digest_date, config.sources, as_of=parse_date(args.as_of) if args.as_of else None)
    print(f"Prepared opening special-issue section; source snapshot: {path}")
    return 0


def cmd_validate_digest(args: argparse.Namespace) -> int:
    candidate = json.loads(Path(args.candidate_digest).read_text(encoding="utf-8"))
    markdown = Path(args.reviewed_digest).read_text(encoding="utf-8")
    delivery_metadata(Path(args.reviewed_digest), markdown, candidate["digest_key"])
    errors = validate_reviewed_digest(candidate, markdown)
    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        print(f"Digest validation failed: {len(errors)} issue(s).", file=sys.stderr)
        return 1
    print("Digest validation passed.")
    return 0


def cmd_render_digest(args: argparse.Namespace) -> int:
    reviewed_path = Path(args.reviewed_digest)
    output_dir = Path(args.output_dir) if args.output_dir else reviewed_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_body = reviewed_path.read_text(encoding="utf-8")
    parsed_subject, body = extract_subject(markdown_body)
    reviewed = parse_reviewed_digest(markdown_body)
    require_valid_structured_digest(markdown_body, reviewed, args.full_html)
    output_stem = reviewed_path.stem
    written_paths: list[Path] = []
    if reviewed is None:
        subject = parsed_subject or "Weekly journal digest preview"
        plain_text_body = format_legacy_email_body(body, args.recipient_name or "Reader")
        text_path = output_dir / f"{output_stem}.preview.txt"
        text_path.write_text(f"Subject: {subject}\n\n{plain_text_body}", encoding="utf-8")
        written_paths.append(text_path)
    else:
        text_path = output_dir / f"{output_stem}.preview.txt"
        html_path = output_dir / f"{output_stem}.preview.html"
        pdf_path = output_dir / f"{output_stem}.preview.pdf"
        plain_text_body = render_summary_plain_text(reviewed, args.recipient_name)
        html_body = render_summary_html(reviewed, args.recipient_name, include_full_digest=args.full_html)
        text_path.write_text(f"Subject: {reviewed.subject}\n\n{plain_text_body}", encoding="utf-8")
        html_path.write_text(html_body, encoding="utf-8")
        pdf_path.write_bytes(render_curated_digest_pdf(reviewed))
        written_paths.extend([text_path, html_path, pdf_path])
    print("Wrote digest preview artifacts:")
    for path in written_paths:
        print(f"- {path}")
    return 0


def cmd_send_digest(args: argparse.Namespace) -> int:
    if args.test and not args.recipient:
        raise ValueError("--test requires an explicit --recipient.")
    config = load_config(args.config)
    repo_root = repo_root_for_config(args.config)
    state_dir = resolve_state_dir(args.config, args.state_dir or config.state_dir)
    store = StateStore(state_dir / "digest.db")
    digest_date = parse_date(args.digest_date) if args.digest_date else date.today()
    digest_key = digest_date.isoformat()
    if args.test:
        digest_key = f"test:{digest_key}"
    recipients = resolve_recipients(args.config, config.recipients_file, args.recipient)
    if not recipients:
        raise ValueError(
            "At least one recipient is required via --recipient, WJD_GMAIL_RECIPIENT, or the configured recipients file."
        )
    reviewed_path = Path(args.reviewed_digest)
    markdown_body = reviewed_path.read_text(encoding="utf-8")
    special_issues = delivery_metadata(reviewed_path, markdown_body, digest_date.isoformat())
    if special_issues and special_issues.get("announcement_key") and not store.announcement_pending(special_issues["announcement_key"], digest_date.isoformat()):
        raise ValueError("The one-time announcement was already delivered; rerun prepare-special-issues for this digest.")
    parsed_subject, body = extract_subject(markdown_body)
    subject = args.subject or parsed_subject or default_subject(digest_date)
    if args.test:
        subject = f"[TEST] {subject}"
    reviewed = parse_reviewed_digest(markdown_body)
    require_valid_structured_digest(markdown_body, reviewed, args.full_html)
    plain_text_body = None
    html_body = None
    pdf_bytes = None
    attachments: list[EmailAttachment] = []
    if reviewed is not None:
        pdf_bytes = render_curated_digest_pdf(reviewed)
        attachment_path = reviewed_path.with_suffix(".pdf")
        attachment_path.write_bytes(pdf_bytes)
        full_html_path = reviewed_path.with_suffix(".html")
        full_html_body = render_full_digest_html(reviewed)
        full_html_path.write_text(full_html_body, encoding="utf-8")
        attachments.append(
            EmailAttachment(
                filename=attachment_path.name,
                content=pdf_bytes,
                mime_type="application/pdf",
            )
        )
        if args.full_html:
            attachments.append(
                EmailAttachment(
                    filename=full_html_path.name,
                    content=full_html_body.encode("utf-8"),
                    mime_type="text/html",
                )
            )
    if special_issues and special_issues.get("coverage_text"):
        coverage_path = reviewed_path.with_suffix(".coverage.txt")
        coverage_path.write_text(special_issues["coverage_text"], encoding="utf-8")
        attachments.append(EmailAttachment(filename=coverage_path.name, content=special_issues["coverage_text"].encode("utf-8"), mime_type="text/plain"))
    recipients_to_send = [
        recipient
        for recipient in recipients
        if args.force or not store.has_sent_digest(digest_key, recipient.email)
    ]
    if not recipients_to_send:
        print(f"Digest {digest_key} was already sent to all configured recipients. Use --force to resend.")
        return 0
    sent_any = False
    try:
        sender = GmailSender.from_env()
        for recipient in recipients:
            if recipient not in recipients_to_send:
                print(f"Digest {digest_key} was already sent to {recipient.email}. Use --force to resend.")
                continue
            plain_text_body = None
            html_body = None
            if reviewed is None:
                message_id = sender.send_markdown(
                    recipient.email,
                    subject,
                    format_legacy_email_body(body, recipient.salutation_name),
                )
            else:
                plain_text_body = render_summary_plain_text(reviewed, recipient.salutation_name)
                html_body = render_summary_html(
                    reviewed,
                    recipient.salutation_name,
                    include_full_digest=args.full_html,
                )
                message_id = sender.send_digest_package(
                    recipient.email,
                    subject,
                    plain_text_body,
                    html_body,
                    attachments,
                )
            store.record_sent_digest(
                digest_key=digest_key,
                recipient=recipient.email,
                subject=subject,
                body=markdown_body,
                sent_at=utc_now().isoformat(),
                message_id=message_id,
                special_issues=special_issues if not args.test else None,
            )
            sent_any = True
            print(f"Sent digest {digest_key} to {recipient.email}. Gmail message id: {message_id}")
    except Exception as exc:
        detail = describe_delivery_error(exc)
        if sent_any:
            print(
                f"Digest {digest_key} stopped after at least one successful send. "
                f"Remaining recipients were not delivered: {detail}",
                file=sys.stderr,
            )
        else:
            print(
                f"Digest {digest_key} was not sent. No send record was written: {detail}",
                file=sys.stderr,
            )
        return 1
    if sent_any and not args.test:
        maybe_commit_and_push_log_artifacts(repo_root, digest_key, reviewed_path)
    return 0


def require_valid_structured_digest(markdown_body: str, reviewed: object, full_html: bool) -> None:
    structured = any(
        line.strip() in {"## Summary", "## Email Summary", "## Highlights", "## Full Curated Digest"}
        for line in markdown_body.splitlines()
    )
    if reviewed is None and (structured or full_html):
        raise ValueError("Invalid structured digest: require Subject, Summary, Highlights, and Full Curated Digest; refusing plain-text fallback.")


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_local_env(
    config_path: str | Path | None = None,
    env_paths: list[Path] | None = None,
) -> None:
    if env_paths is None:
        base_dir = repo_root_for_config(config_path) if config_path else REPO_ROOT
        paths = [base_dir / ".env.local", base_dir / ".env"]
    else:
        paths = env_paths
    for path in paths:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                os.environ.setdefault(key, value)


def resolve_state_dir(config_path: str | Path, state_dir_value: str) -> Path:
    return resolve_repo_path(config_path, state_dir_value)


def resolve_repo_path(config_path: str | Path, configured_path: str) -> Path:
    path = Path(configured_path)
    if path.is_absolute():
        return path
    return repo_root_for_config(config_path) / path


def repo_root_for_config(config_path: str | Path) -> Path:
    config_file = Path(config_path).resolve()
    config_parent = config_file.parent
    return config_parent.parent if config_parent.name == "config" else config_parent


def resolve_recipients(
    config_path: str | Path,
    recipients_file_value: str,
    recipient_override: str | None,
) -> list[Recipient]:
    if recipient_override:
        email = recipient_override.strip()
        if not email or any(char in email for char in "\r\n,;") or email.count("@") != 1:
            raise ValueError("--recipient must be a single email address.")
        recipients_path = resolve_repo_path(config_path, recipients_file_value)
        if recipients_path.exists():
            for recipient in load_recipients(recipients_path):
                if recipient.email.casefold() == email.casefold():
                    return [recipient]
        return [Recipient(email=email)]
    env_recipients = os.environ.get("WJD_GMAIL_RECIPIENT")
    if env_recipients:
        return dedupe_recipients(
            Recipient(email=recipient.strip())
            for recipient in env_recipients.split(",")
            if recipient.strip()
        )
    recipients_path = resolve_repo_path(config_path, recipients_file_value)
    if not recipients_path.exists():
        return []
    return load_recipients(recipients_path)


def load_recipients(recipients_path: str | Path) -> list[Recipient]:
    raw = json.loads(Path(recipients_path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        entries = raw.get("recipients", [])
    elif isinstance(raw, list):
        entries = raw
    else:
        raise ValueError("Recipients file must contain a list or a {'recipients': [...]} object.")
    recipients: list[Recipient] = []
    for entry in entries:
        if isinstance(entry, str):
            email = entry.strip()
            active = True
            name = None
        else:
            email = str(entry.get("email", "")).strip()
            active = bool(entry.get("active", True))
            name = str(entry.get("name", "")).strip() or None
        if email and active:
            recipients.append(Recipient(email=email, name=name))
    return dedupe_recipients(recipients)


def dedupe_recipients(recipients: list[Recipient] | tuple[Recipient, ...] | object) -> list[Recipient]:
    seen: set[str] = set()
    ordered: list[Recipient] = []
    for recipient in recipients:
        if recipient.email not in seen:
            seen.add(recipient.email)
            ordered.append(recipient)
    return ordered


def format_legacy_email_body(body: str, recipient_name: str) -> str:
    return (
        f"Dear {recipient_name},\n\n"
        f"{body.strip()}\n\n"
        "COMAP Journal Bot\n\n"
        f"{DELIVERY_PREFERENCES_TEXT}\n"
    )


def maybe_commit_and_push_log_artifacts(
    repo_root: Path,
    digest_key: str,
    reviewed_path: Path,
) -> None:
    reviewed_path = reviewed_path.resolve()
    repo_root = repo_root.resolve()
    expected_log_dir = (repo_root / "logs" / digest_key).resolve()
    if reviewed_path.parent != expected_log_dir:
        return
    if not _git_is_repository(repo_root):
        return
    artifact_paths = [
        expected_log_dir / f"candidate_digest-{digest_key}.json",
        reviewed_path,
        reviewed_path.with_suffix(".pdf"),
        reviewed_path.with_suffix(".html"),
        reviewed_path.with_suffix(".special-issues.json"),
        reviewed_path.with_suffix(".coverage.txt"),
    ]
    artifact_paths = [path.resolve() for path in artifact_paths if path.exists()]
    if not artifact_paths:
        return
    allowed_paths = {str(path.relative_to(repo_root)) for path in artifact_paths}
    status = _git(repo_root, "status", "--porcelain", "--untracked-files=all")
    if status.returncode != 0:
        print(f"Skipping git auto-push for {digest_key}: could not inspect git status.")
        return
    status_lines = [line for line in status.stdout.splitlines() if line.strip()]
    if not status_lines:
        return
    changed_paths: list[str] = []
    for line in status_lines:
        path = _parse_git_status_path(line)
        if path is None:
            print(f"Skipping git auto-push for {digest_key}: unsupported git status entry `{line}`.")
            return
        changed_paths.append(path)
    unrelated_paths = sorted(path for path in changed_paths if path not in allowed_paths)
    if unrelated_paths:
        preview = ", ".join(unrelated_paths[:3])
        if len(unrelated_paths) > 3:
            preview += ", ..."
        print(
            f"Skipping git auto-push for {digest_key}: repo has unrelated changes ({preview})."
        )
        return
    add_result = _git(repo_root, "add", "--", *sorted(allowed_paths))
    if add_result.returncode != 0:
        print(f"Skipping git auto-push for {digest_key}: could not stage log artifacts.")
        return
    staged_result = _git(
        repo_root,
        "diff",
        "--cached",
        "--name-only",
        "--",
        *sorted(allowed_paths),
    )
    if staged_result.returncode != 0 or not staged_result.stdout.strip():
        return
    commit_result = _git(repo_root, "commit", "-m", f"Add digest log for {digest_key}")
    if commit_result.returncode != 0:
        error = commit_result.stderr.strip() or commit_result.stdout.strip()
        print(f"Skipping git auto-push for {digest_key}: commit failed ({error}).")
        return
    push_result = _git_push_current_branch(repo_root)
    if push_result.returncode == 0:
        print(f"Committed and pushed digest log for {digest_key}.")
        return
    error = push_result.stderr.strip() or push_result.stdout.strip()
    print(
        f"Committed digest log for {digest_key}, but push failed"
        f"{f' ({error})' if error else '.'}"
    )


def _git_is_repository(repo_root: Path) -> bool:
    result = _git(repo_root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_push_current_branch(repo_root: Path) -> subprocess.CompletedProcess[str]:
    upstream = _git(
        repo_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
    )
    if upstream.returncode == 0 and upstream.stdout.strip():
        return _git(repo_root, "push")
    branch = _git(repo_root, "branch", "--show-current")
    remote = _git(repo_root, "remote")
    branch_name = branch.stdout.strip()
    remotes = [line.strip() for line in remote.stdout.splitlines() if line.strip()]
    if branch.returncode != 0 or not branch_name or "origin" not in remotes:
        return subprocess.CompletedProcess(
            args=["git", "push"],
            returncode=1,
            stdout="",
            stderr="No upstream or origin remote configured.",
        )
    return _git(repo_root, "push", "-u", "origin", branch_name)


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def _parse_git_status_path(line: str) -> str | None:
    if len(line) < 4:
        return None
    path = line[3:].strip()
    if not path or " -> " in path:
        return None
    return path


def re_split_recipient_name(value: str) -> list[str]:
    return [
        piece
        for chunk in value.replace(".", " ").replace("_", " ").replace("-", " ").split()
        for piece in [chunk]
    ]


def default_subject(digest_date: date) -> str:
    windows = compute_weekly_windows(digest_date)
    return (
        "Weekly journal digest for "
        f"{windows.new_this_week_start} to {windows.new_this_week_end}"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
