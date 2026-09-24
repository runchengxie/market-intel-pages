import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.generate_codex_commentary import run
from scripts.generate_daily_summary import run as run_summary
from scripts.generate_insights import run as run_insight
from tests.test_insights import analysis, sources


class CodexCommentaryTests(unittest.TestCase):
    def test_cloud_insight_can_supply_summary_when_minimax_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports, summaries, insights = (
                root / name for name in ("reports.json", "summaries.json", "insights.json")
            )
            reports.write_text(
                json.dumps({"schema_version": "market_intel_pages.reports.v1", "reports": sources()})
            )
            summaries.write_text(json.dumps({"summaries": []}))
            run_insight(reports, insights, provider="gemini", api_key="test", generator=lambda *_: analysis())
            self.assertEqual(
                "generated summary",
                run_summary(reports, summaries, summaries, None, insights_path=insights),
            )
            self.assertEqual("gemini", json.loads(summaries.read_text())["summaries"][0]["provider"])

    def test_valid_cli_result_creates_both_indices_and_reuses_them(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports, summaries, insights = (
                root / name for name in ("reports.json", "summaries.json", "insights.json")
            )
            reports.write_text(
                json.dumps({"schema_version": "market_intel_pages.reports.v1", "reports": sources()})
            )

            def cli(arguments, **kwargs):
                self.assertIn("read-only", arguments)
                self.assertNotIn("GH_TOKEN", kwargs["env"])
                Path(arguments[arguments.index("--output-last-message") + 1]).write_text(
                    json.dumps(analysis())
                )
                return SimpleNamespace(returncode=0)

            with patch("scripts.generate_codex_commentary.subprocess.run", side_effect=cli) as command:
                self.assertEqual(
                    "generated validated Codex commentary",
                    run(reports, summaries, insights, root / "archive", root / "work", Path("/bin/codex")),
                )
                self.assertEqual(
                    "reused validated Codex commentary",
                    run(reports, summaries, insights, root / "archive", root / "work", Path("/bin/codex")),
                )
            self.assertEqual(1, command.call_count)
            self.assertEqual("codex", json.loads(summaries.read_text())["summaries"][0]["provider"])
            self.assertEqual("codex", json.loads(insights.read_text())["insights"][0]["provider"])

    def test_invalid_cli_analysis_does_not_write_indices(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports, summaries, insights = (
                root / name for name in ("reports.json", "summaries.json", "insights.json")
            )
            reports.write_text(
                json.dumps({"schema_version": "market_intel_pages.reports.v1", "reports": sources()})
            )

            def cli(arguments, **_):
                bad = analysis()
                bad["changes"][0]["text"] = "上涨率 99.9%。"
                Path(arguments[arguments.index("--output-last-message") + 1]).write_text(json.dumps(bad))
                return SimpleNamespace(returncode=0)

            with patch("scripts.generate_codex_commentary.subprocess.run", side_effect=cli):
                with self.assertRaises(ValueError):
                    run(reports, summaries, insights, root / "archive", root / "work", Path("/bin/codex"))
            self.assertFalse(summaries.exists())
            self.assertFalse(insights.exists())
