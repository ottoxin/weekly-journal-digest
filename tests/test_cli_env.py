from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from weekly_journal_digest.cli import load_local_env


class CliEnvTests(unittest.TestCase):
    def test_load_local_env_sets_missing_values_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env.local"
            env_path.write_text(
                "\n".join(
                    [
                        "# comment",
                        "WJD_SEMANTIC_SCHOLAR_API_KEY=test-key",
                        "WJD_CROSSREF_MAILTO=test@example.com",
                    ]
                ),
                encoding="utf-8",
            )
            previous_key = os.environ.pop("WJD_SEMANTIC_SCHOLAR_API_KEY", None)
            previous_mailto = os.environ.get("WJD_CROSSREF_MAILTO")
            os.environ["WJD_CROSSREF_MAILTO"] = "existing@example.com"
            try:
                load_local_env(env_paths=[env_path])
                self.assertEqual(os.environ.get("WJD_SEMANTIC_SCHOLAR_API_KEY"), "test-key")
                self.assertEqual(os.environ.get("WJD_CROSSREF_MAILTO"), "existing@example.com")
            finally:
                if previous_key is None:
                    os.environ.pop("WJD_SEMANTIC_SCHOLAR_API_KEY", None)
                else:
                    os.environ["WJD_SEMANTIC_SCHOLAR_API_KEY"] = previous_key
                if previous_mailto is None:
                    os.environ.pop("WJD_CROSSREF_MAILTO", None)
                else:
                    os.environ["WJD_CROSSREF_MAILTO"] = previous_mailto


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
