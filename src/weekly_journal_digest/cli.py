from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .adapters import build_adapter_registry
from .config import load_config
from .digest import build_candidate_digest, compute_weekly_windows
from .emailing import EmailAttachment, GmailSender, extract_subject
from .enrichment import build_metadata_enricher
from .filters import should_include_record
from .reviewed_digest import (
    parse_reviewed_digest,
    render_curated_digest_pdf,
    render_summary_html,
    render_summary_plain_text,
)
from .storage import StateStore


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "sources.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
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
        help="Build candidate_digest.json for Monday review.",
    )
    build_parser_.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    build_parser_.add_argument("--state-dir", default=None)
    build_parser_.add_argument("--digest-date", default=None, help="Digest date in YYYY-MM-DD.")
    build_parser_.add_argument("--output", default=None)
    build_parser_.set_defaults(func=cmd_build_weekly_digest)

    send_parser = subparsers.add_parser("send-digest", help="Send the reviewed digest via Gmail API.")
    send_parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    send_parser.add_argument("--state-dir", default=None)
    send_parser.add_argument("--digest-date", default=None, help="Digest date in YYYY-MM-DD.")
    send_parser.add_argument("--reviewed-digest", required=True)
    send_parser.add_argument("--recipient", default=None)
    send_parser.add_argument("--subject", default=None)
    send_parser.add_argument("--force", action="store_true")
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
    lookback_days = args.lookback_days or config.default_lookback_days
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
            records = enricher.enrich_records(records)
            included = []
            for record in records:
                include, reason = should_include_record(source, record, config.social_science_keywords)
                if include:
                    record.relevance_status = reason
                    included.append(record)
            store.upsert_articles(included, seen_at=seen_at)
            stored_total += len(included)
            archive_payload["sources"].append(
                {
                    "source_id": source.id,
                    "journal": source.journal,
                    "retrieved": len(records),
                    "stored": len(included),
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
    payload = build_candidate_digest(store, config, digest_date, output_path)
    print(
        f"Wrote candidate digest to {output_path} "
        f"({len(payload['sections']['new_this_week'])} new / "
        f"{len(payload['sections']['previous_week_catch_up'])} catch-up / "
        f"{len(payload['sections']['late_additions'])} late additions)."
    )
    return 0


def cmd_send_digest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    state_dir = resolve_state_dir(args.config, args.state_dir or config.state_dir)
    store = StateStore(state_dir / "digest.db")
    digest_date = parse_date(args.digest_date) if args.digest_date else date.today()
    recipient = args.recipient or os.environ.get("WJD_GMAIL_RECIPIENT")
    if not recipient:
        raise ValueError("Recipient is required via --recipient or WJD_GMAIL_RECIPIENT.")
    digest_key = digest_date.isoformat()
    reviewed_path = Path(args.reviewed_digest)
    markdown_body = reviewed_path.read_text(encoding="utf-8")
    parsed_subject, body = extract_subject(markdown_body)
    subject = args.subject or parsed_subject or default_subject(digest_date)
    if store.has_sent_digest(digest_key, recipient) and not args.force:
        print(f"Digest {digest_key} was already sent to {recipient}. Use --force to resend.")
        return 0
    sender = GmailSender.from_env()
    reviewed = parse_reviewed_digest(markdown_body)
    if reviewed is None:
        message_id = sender.send_markdown(recipient, subject, body)
    else:
        plain_text_body = render_summary_plain_text(reviewed)
        html_body = render_summary_html(reviewed)
        pdf_bytes = render_curated_digest_pdf(reviewed)
        attachment_path = reviewed_path.with_suffix(".pdf")
        attachment_path.write_bytes(pdf_bytes)
        message_id = sender.send_digest_package(
            recipient,
            subject,
            plain_text_body,
            html_body,
            [EmailAttachment(filename=attachment_path.name, content=pdf_bytes, mime_type="application/pdf")],
        )
    store.record_sent_digest(
        digest_key=digest_key,
        recipient=recipient,
        subject=subject,
        body=markdown_body,
        sent_at=utc_now().isoformat(),
        message_id=message_id,
    )
    print(f"Sent digest {digest_key} to {recipient}.")
    return 0


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_state_dir(config_path: str | Path, state_dir_value: str) -> Path:
    state_dir = Path(state_dir_value)
    if state_dir.is_absolute():
        return state_dir
    config_file = Path(config_path).resolve()
    config_parent = config_file.parent
    repo_root = config_parent.parent if config_parent.name == "config" else config_parent
    return repo_root / state_dir


def default_subject(digest_date: date) -> str:
    windows = compute_weekly_windows(digest_date)
    return (
        "Weekly journal digest for "
        f"{windows.new_this_week_start} to {windows.new_this_week_end}"
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
