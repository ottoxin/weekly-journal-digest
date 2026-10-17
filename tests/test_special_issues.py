from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from weekly_journal_digest.cli import main
from weekly_journal_digest.reviewed_digest import parse_reviewed_digest, render_summary_html, render_full_digest_html, render_summary_plain_text
from weekly_journal_digest.special_issues import NOTICE_KEY, prepare_updates, eligible_calls, render_updates, delivery_metadata
from weekly_journal_digest.storage import StateStore


class SpecialIssueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'companion'
        public = self.repo / 'data/public'
        public.mkdir(parents=True)
        (self.repo / 'config').mkdir()
        self.call = dict(title='A current call', journal='Test Journal', source_id='test', source_url='https://example.org/call', status='active', deadline='2026-10-10', opportunity_type='call-for-papers', snippet='Original')
        self.status = {'health': {'special_issue_status': 'current', 'special_issue_run': {'automated_publisher_journal_ids': ['test']}}, 'run': {'run_started_at': '2026-09-07T06:00:00+00:00', 'errors': []}}
        (public / 'special_issues.jsonl').write_text(json.dumps(self.call)+'\n')
        (public / 'special_issue_collection.json').write_text(json.dumps(self.status['run']))
        (public / 'health.json').write_text(json.dumps(self.status['health']))
        (public / 'journals.json').write_text(json.dumps([dict(id='test', title='Test Journal', active=True)]))
        (self.repo / 'config/special_issue_sources.yaml').write_text('sources: []')
        self.store = StateStore(self.root / '.state/digest.db')
        self.reviewed = self.root / 'reviewed.md'
        self.reviewed.write_text('Subject: Weekly journal digest for 2026-08-31 to 2026-09-06\n\n## Summary\n\nArticle overview.\n\n## Highlights\n\n## Full Curated Digest\n\nNo qualifying articles.\n')
        self.config = self.root / 'sources.yaml'
        self.config.write_text('sources: []\nstate_dir: .state\n')

    def prepare(self):
        prepare_updates(self.repo, self.reviewed, self.store, '2026-09-07', [])

    def test_preparation_is_idempotent_and_front_renders_everywhere(self):
        self.prepare()
        original = self.reviewed.read_text()
        self.prepare()
        self.assertEqual(self.reviewed.read_text(), original)
        reviewed = parse_reviewed_digest(original)
        for output in [render_summary_html(reviewed), render_full_digest_html(reviewed), render_summary_plain_text(reviewed)]:
            self.assertLess(output.index('Special Issue Updates'), output.index('Article overview.'))
            self.assertIn('https://example.org/call', output)
        self.assertTrue(self.store.announcement_pending(NOTICE_KEY, '2026-09-14'))

    def test_updates_ignore_seen_timestamps_but_include_changes_and_deadlines(self):
        identical = {**self.call, 'last_seen_at': '2026-09-07'}
        result = render_updates([identical], [self.call], date(2026,9,7), self.status)
        self.assertIn('No new or changed', result)
        result = render_updates([{**self.call, 'deadline': '2026-09-10'}], [self.call], date(2026,9,7), self.status)
        self.assertIn('Updated', result)
        near = {**self.call, 'deadline': '2026-09-10'}
        self.assertIn('Deadline within 14 days', render_updates([near], [near], date(2026,9,7), self.status))

    def test_expired_and_unverified_calls_are_excluded_and_stale_snapshot_rejected(self):
        rows = [self.call, {**self.call, 'source_url': 'https://example.org/expired', 'deadline': '2026-09-06'}, {**self.call, 'source_url': 'https://example.org/unverified', 'status': 'unverified'}]
        (self.repo / 'data/public/special_issues.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
        calls, _ = eligible_calls(self.repo, date(2026,9,7))
        self.assertEqual(calls, [self.call])
        with self.assertRaisesRegex(ValueError, 'stale'):
            eligible_calls(self.repo, date(2026,9,20))

    def test_delivery_rejects_changed_or_missing_sidecar(self):
        self.prepare()
        markdown = self.reviewed.read_text()
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            delivery_metadata(self.reviewed, markdown.replace('A current call', 'Wrong call'), '2026-09-07')
        self.reviewed.with_suffix('.special-issues.json').unlink()
        with self.assertRaisesRegex(ValueError, 'snapshot'):
            delivery_metadata(self.reviewed, markdown, '2026-09-07')

    def test_recent_collection_does_not_reverify_old_manual_call(self):
        (self.repo / 'config/special_issue_sources.yaml').write_text('sources:\n  - id: test\n    source_type: manual\n    verified_on: "2026-07-30"\n')
        calls, status = eligible_calls(self.repo, date(2026, 9, 7))
        self.assertEqual(calls, [])
        self.assertEqual(status['stale_manual'], ['Test Journal'])

    def test_refresh_checks_calls_today_without_changing_article_edition(self):
        self.status['run']['run_started_at'] = '2026-09-12T06:00:00+00:00'
        (self.repo / 'data/public/special_issue_collection.json').write_text(json.dumps(self.status['run']))
        rows = [self.call, {**self.call, 'source_url': 'https://example.org/ended', 'deadline': '2026-09-10'}]
        (self.repo / 'data/public/special_issues.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.prepare()
        prepare_updates(self.repo, self.reviewed, self.store, '2026-09-07', [], as_of=date(2026, 9, 12))
        markdown = self.reviewed.read_text()
        self.assertIn('Calls checked: 2026-09-12.', markdown)
        self.assertNotIn('https://example.org/ended', markdown)
        self.assertEqual(delivery_metadata(self.reviewed, markdown, '2026-09-07')['digest_key'], '2026-09-07')

    def test_only_successful_production_send_consumes_announcement_and_baseline(self):
        self.prepare()
        args = ['send-digest', '--config', str(self.config), '--digest-date', '2026-09-07', '--reviewed-digest', str(self.reviewed), '--recipient', 'otto@example.com', '--full-html']
        sender = MagicMock()
        sender.send_digest_package.return_value = 'accepted'
        with patch('weekly_journal_digest.cli.GmailSender.from_env', return_value=sender):
            self.assertEqual(main(args + ['--test']), 0)
            attachments = sender.send_digest_package.call_args.args[4]
            self.assertEqual(attachments[-1].mime_type, 'text/plain')
            self.assertTrue(attachments[-1].filename.endswith('.coverage.txt'))
            self.assertIn(b'Test Journal', attachments[-1].content)
            self.assertTrue(self.store.announcement_pending(NOTICE_KEY, '2026-09-14'))
            self.assertIsNone(self.store.last_special_issue_snapshot('2026-09-14'))
            sender.send_digest_package.side_effect = RuntimeError('failed before send')
            self.assertEqual(main(args), 1)
            self.assertTrue(self.store.announcement_pending(NOTICE_KEY, '2026-09-14'))
            sender.send_digest_package.side_effect = None
            self.assertEqual(main(args), 0)
        self.assertFalse(self.store.announcement_pending(NOTICE_KEY, '2026-09-14'))
        self.assertTrue(self.store.announcement_pending(NOTICE_KEY, '2026-09-07'))
        self.assertEqual(self.store.last_special_issue_snapshot('2026-09-14'), [self.call])

    def test_source_failure_is_not_reported_as_complete_coverage(self):
        status = {'health': self.status['health'], 'run': {**self.status['run'], 'errors': [{'source_id': 'failed-source'}]}}
        self.assertIn('Coverage warning', render_updates([], [], date(2026,9,7), status))


if __name__ == '__main__':
    unittest.main()
