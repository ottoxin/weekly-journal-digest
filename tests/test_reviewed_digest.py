from __future__ import annotations

import unittest

from weekly_journal_digest.reviewed_digest import (
    parse_reviewed_digest,
    render_curated_digest_pdf,
    render_summary_html,
    render_summary_plain_text,
)


SAMPLE_REVIEWED_DIGEST = """Subject: Weekly journal digest for 2026-03-23 to 2026-03-29

## Summary

This week brought a focused set of papers worth your attention.

- Political communication and AI methods are the strongest themes.
- The attached PDF is organized by journal for quick navigation.

## Collection Snapshot

- Total collected candidates: 25
- New This Week candidates: 12
- Previous Week Catch-Up candidates: 8
- Late Additions candidates: 5
- Curated digest below: 4 new, 2 catch-up, 1 late addition

## Highlights

- **Political behavior in online networks**
  Journal: Nature Human Behaviour
  Published: 2026-03-27
  Why it matters: It links platform dynamics to core questions about political communication.
  Link: https://doi.org/10.1000/example

- **Field experiments at scale**
  Journal: Science
  Published: 2026-03-26
  Why it matters: It shows how causal evidence can travel into real policy settings.
  Link: https://doi.org/10.1000/example-2

## Full Curated Digest

### New This Week

#### Nature Human Behaviour
- **Political behavior in online networks**
  Published: 2026-03-27
  Link: https://doi.org/10.1000/example
  Abstract: Example abstract text.

### Previous Week Catch-Up

- Science | 2026-03-20 | Field experiments at scale | https://doi.org/10.1000/example-2
"""


class ReviewedDigestTests(unittest.TestCase):
    def test_parse_reviewed_digest_extracts_sections(self) -> None:
        reviewed = parse_reviewed_digest(SAMPLE_REVIEWED_DIGEST)
        self.assertIsNotNone(reviewed)
        assert reviewed is not None
        self.assertEqual(reviewed.subject, "Weekly journal digest for 2026-03-23 to 2026-03-29")
        self.assertEqual(len(reviewed.collection_snapshot), 5)
        self.assertEqual(len(reviewed.highlights), 2)
        self.assertIn("### New This Week", reviewed.full_curated_digest_markdown)
        self.assertIn("Political communication and AI methods are the strongest themes.", reviewed.summary)

    def test_render_summary_outputs_include_highlights(self) -> None:
        reviewed = parse_reviewed_digest(SAMPLE_REVIEWED_DIGEST)
        assert reviewed is not None
        plain_text = render_summary_plain_text(reviewed)
        html = render_summary_html(reviewed)
        self.assertIn("The full curated digest is attached as a PDF.", plain_text)
        self.assertIn("Political behavior in online networks", plain_text)
        self.assertNotIn("Collection Snapshot", plain_text)
        self.assertNotIn("Collection Snapshot", html)
        self.assertIn("The attached PDF includes the full curated digest, abstract-level details, and a journal table of contents.", html)
        self.assertIn("<ul", html)
        self.assertIn("Open article", html)

    def test_render_curated_digest_pdf_returns_pdf_bytes(self) -> None:
        reviewed = parse_reviewed_digest(SAMPLE_REVIEWED_DIGEST)
        assert reviewed is not None
        pdf_bytes = render_curated_digest_pdf(reviewed)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))

    def test_parse_reviewed_digest_accepts_legacy_email_summary_header(self) -> None:
        legacy = SAMPLE_REVIEWED_DIGEST.replace("## Summary", "## Email Summary")
        reviewed = parse_reviewed_digest(legacy)
        self.assertIsNotNone(reviewed)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
