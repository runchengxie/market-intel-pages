import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_site import build_site, refresh_astro
from scripts.sync_public_snapshot import sync_snapshot
from tests.test_chart_contract import public_chart, rehash

REPORT_SCHEMA = "market_intel_pages.reports.v1"
SUMMARY_SCHEMA = "market_intel_pages.daily_summaries.v1"


def create_site(root: Path, session_count: int = 6) -> None:
    (root / "data").mkdir(parents=True)
    (root / "reports").mkdir()
    for name in (
        "index.html",
        "app.js",
        "styles.css",
        "summary-utils.js",
        "report-markdown.js",
        "market-daily-utils.js",
        "theme-utils.js",
    ):
        (root / name).write_text(name, encoding="utf-8")

    reports = []
    for day in range(1, session_count + 1):
        date = f"2026-09-{day:02d}"
        for kind in ("morning", "evening"):
            report_id = f"{date}-{kind}"
            source_url = f"reports/{report_id}.md"
            reports.append(
                {
                    "id": report_id,
                    "date": date,
                    "kind": kind,
                    "title": report_id,
                    "summary": "sample",
                    "sections": [],
                    "source_url": source_url,
                }
            )
            (root / source_url).write_text(f"# {report_id}\n", encoding="utf-8")

    (root / "data/reports.json").write_text(
        json.dumps(
            {
                "schema_version": REPORT_SCHEMA,
                "generated_at": "2026-09-16T08:00:00+08:00",
                "reports": reports,
            }
        ),
        encoding="utf-8",
    )
    (root / "data/daily_summaries.json").write_text(
        json.dumps(
            {
                "schema_version": SUMMARY_SCHEMA,
                "summaries": [],
            }
        ),
        encoding="utf-8",
    )


class BuildSiteTests(unittest.TestCase):
    def test_build_copies_only_indexed_public_charts(self) -> None:
        sync_snapshot(self.root, self.archive)
        chart_dir = self.root / "data/charts"
        chart_dir.mkdir()
        current = public_chart()
        current["date"] = "2026-09-02"
        current["report_id"] = "2026-09-02-morning"
        current["charts"][0]["points"][0]["observation_date"] = "2026-09-02"
        (chart_dir / "2026-09-02-morning.json").write_text(json.dumps(rehash(current)), encoding="utf-8")
        (chart_dir / "2026-09-01-morning.json").write_text("stale private data", encoding="utf-8")
        build_site(self.root, self.output)
        self.assertTrue((self.output / "data/charts/2026-09-02-morning.json").is_file())
        self.assertFalse((self.output / "data/charts/2026-09-01-morning.json").exists())

    def test_build_rejects_candidate_chart_in_current_window(self) -> None:
        sync_snapshot(self.root, self.archive)
        chart_dir = self.root / "data/charts"
        chart_dir.mkdir()
        current = public_chart()
        current["date"] = "2026-09-02"
        current["report_id"] = "2026-09-02-morning"
        current["publication"] = "candidate"
        current["charts"][0]["points"][0]["observation_date"] = "2026-09-02"
        (chart_dir / "2026-09-02-morning.json").write_text(json.dumps(rehash(current)), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "public"):
            build_site(self.root, self.output)

    def test_failed_build_preserves_previous_artifact(self) -> None:
        sync_snapshot(self.root, self.archive)
        build_site(self.root, self.output)
        (self.output / "index.html").write_text("published artifact", encoding="utf-8")
        (self.root / "data/charts").mkdir()
        (self.root / "data/charts/2026-09-02-morning.json").write_text('{"publication":"candidate"}')
        with self.assertRaises(ValueError):
            build_site(self.root, self.output)
        self.assertEqual("published artifact", (self.output / "index.html").read_text(encoding="utf-8"))

    def test_build_emits_health_and_optional_insights(self) -> None:
        sync_snapshot(self.root, self.archive)
        build_site(self.root, self.output)
        health = json.loads((self.output / "data/health.json").read_text())
        self.assertEqual("missing", health["status"])
        self.assertEqual(
            "market_intel_pages.insights.v1",
            json.loads((self.output / "data/insights.json").read_text())["schema_version"],
        )

    def test_build_copies_imported_market_daily_data(self) -> None:
        sync_snapshot(self.root, self.archive)
        payload = {"schema_version": "1.0", "run_id": "daily-2026-09-23"}
        (self.root / "data/market_daily_report.json").write_text(json.dumps(payload), encoding="utf-8")
        (self.root / "reports/2026-09-23-market-daily.txt").write_text("verified text\n", encoding="utf-8")
        (self.root / "reports/2026-09-23-market-daily.md").write_text(
            "# verified markdown\n", encoding="utf-8"
        )
        (self.root / "reports/2026-09-22-market-daily.txt").write_text("stale\n", encoding="utf-8")
        build_site(self.root, self.output)
        self.assertEqual(
            payload,
            json.loads((self.output / "data/market_daily_report.json").read_text()),
        )
        self.assertEqual(
            "verified text\n",
            (self.output / "reports/2026-09-23-market-daily.txt").read_text(),
        )
        self.assertTrue((self.output / "reports/2026-09-23-market-daily.md").is_file())
        self.assertFalse((self.output / "reports/2026-09-22-market-daily.txt").exists())

    def test_build_rejects_claimed_text_format_without_file(self) -> None:
        sync_snapshot(self.root, self.archive)
        (self.root / "data/market_daily_report.json").write_text(
            json.dumps({"run_id": "daily-2026-09-23", "report_formats": ["md", "txt"]}),
            encoding="utf-8",
        )
        (self.root / "reports/2026-09-23-market-daily.md").write_text("# report\n")
        with self.assertRaisesRegex(ValueError, "claimed market daily format missing"):
            build_site(self.root, self.output)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.root = self.directory / "repo"
        self.archive = self.directory / "local-archive"
        self.output = self.directory / "site"
        create_site(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sync_keeps_all_reports_locally_and_only_five_dates_public(self) -> None:
        sync_snapshot(self.root, self.archive)

        local = json.loads((self.archive / "data/reports.json").read_text())
        public = json.loads((self.root / "data/reports.json").read_text())
        self.assertEqual(12, len(local["reports"]))
        self.assertEqual(10, len(public["reports"]))
        self.assertEqual("2026-09-02", min(r["date"] for r in public["reports"]))
        self.assertTrue((self.archive / "reports/2026-09-01-morning.md").exists())
        self.assertFalse((self.root / "reports/2026-09-01-morning.md").exists())

    def test_sync_is_idempotent_for_report_ids(self) -> None:
        sync_snapshot(self.root, self.archive)
        sync_snapshot(self.root, self.archive)

        local = json.loads((self.archive / "data/reports.json").read_text())
        self.assertEqual(12, len(local["reports"]))

    def test_sync_preserves_distinct_summary_source_pairs(self) -> None:
        summaries = []
        for evening_id in ("2026-09-05-evening", "2026-09-06-evening"):
            summaries.append(
                {
                    "date": "2026-09-06",
                    "text": f"note from {evening_id}",
                    "morning_report_id": "2026-09-06-morning",
                    "evening_report_id": evening_id,
                    "generated_at": "2026-09-07T07:00:00+08:00",
                    "model": "test",
                    "prompt_version": "daily-note-v1",
                }
            )
        (self.root / "data/daily_summaries.json").write_text(
            json.dumps(
                {
                    "schema_version": SUMMARY_SCHEMA,
                    "summaries": summaries,
                }
            ),
            encoding="utf-8",
        )

        sync_snapshot(self.root, self.archive)

        local = json.loads((self.archive / "data/daily_summaries.json").read_text())
        pairs = {(row["morning_report_id"], row["evening_report_id"]) for row in local["summaries"]}
        self.assertEqual(
            {
                ("2026-09-06-morning", "2026-09-05-evening"),
                ("2026-09-06-morning", "2026-09-06-evening"),
            },
            pairs,
        )

    def test_sync_rejects_archive_inside_public_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            sync_snapshot(self.root, self.root / "archive")

    def test_sync_counts_a_report_date_even_before_its_morning_report_exists(self) -> None:
        index_path = self.root / "data/reports.json"
        index = json.loads(index_path.read_text())
        index["reports"] = [row for row in index["reports"] if row["id"] != "2026-09-06-morning"]
        index_path.write_text(json.dumps(index), encoding="utf-8")
        (self.root / "reports/2026-09-06-morning.md").unlink()

        sync_snapshot(self.root, self.archive)

        public = json.loads(index_path.read_text())
        public_ids = {row["id"] for row in public["reports"]}
        self.assertIn("2026-09-06-evening", public_ids)
        self.assertNotIn("2026-09-01-morning", public_ids)

    def test_build_site_copies_only_indexed_reports_and_markdown(self) -> None:
        sync_snapshot(self.root, self.archive)
        build_site(self.root, self.output, self.root / "data/daily_summaries.json")

        report_data = json.loads((self.output / "data/reports.json").read_text())
        copied = {path.relative_to(self.output).as_posix() for path in (self.output / "reports").glob("*.md")}
        expected = {report["source_url"] for report in report_data["reports"]}
        self.assertEqual(expected, copied)
        self.assertEqual(10, len(report_data["reports"]))
        self.assertTrue((self.output / "summary-utils.js").is_file())
        self.assertTrue((self.output / "market-daily-utils.js").is_file())
        self.assertTrue((self.output / "report-markdown.js").is_file())
        self.assertEqual(
            "market_intel_pages.daily_summaries.v1",
            json.loads((self.output / "data/daily_summaries.json").read_text())["schema_version"],
        )

    def test_build_rejects_summary_with_unknown_source(self) -> None:
        (self.root / "data/daily_summaries.json").write_text(
            json.dumps(
                {
                    "schema_version": SUMMARY_SCHEMA,
                    "summaries": [
                        {
                            "date": "2026-09-06",
                            "text": "sample",
                            "morning_report_id": "missing-morning",
                            "evening_report_id": "2026-09-06-evening",
                            "generated_at": "2026-09-07T07:00:00+08:00",
                            "model": "test",
                            "prompt_version": "daily-note-v1",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "source report"):
            build_site(self.root, self.output, self.root / "data/daily_summaries.json")


if __name__ == "__main__":
    unittest.main()


def test_real_site_build_overlays_astro_pages_and_keeps_downloads(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "site"
    build_site(root, output)
    index_data = json.loads((output / "data/reports.json").read_text(encoding="utf-8"))
    report_id = index_data["reports"][0]["id"]
    index = (output / "index.html").read_text(encoding="utf-8")
    assert "REPORT ARCHIVE" in index
    assert f"/market-intel-pages/reports/{report_id}/" in index
    assert (output / f"reports/{report_id}/index.html").is_file()
    market = json.loads((output / "data/market_daily_report.json").read_text(encoding="utf-8"))
    market_date = market["run_id"].removeprefix("daily-")
    assert (output / f"reports/{market_date}-market-daily.md").is_file()
    assert (output / f"reports/{market_date}-market-daily.txt").is_file()


def test_refresh_astro_uses_latest_generated_snapshot(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "site"
    build_site(root, output)
    report_id = json.loads((output / "data/reports.json").read_text(encoding="utf-8"))["reports"][0]["id"]
    report = output / f"reports/{report_id}.md"
    report.write_text(report.read_text(encoding="utf-8") + "\n发布后解读标记\n", encoding="utf-8")
    refresh_astro(root, output)
    assert "发布后解读标记" in (output / f"reports/{report_id}/index.html").read_text(encoding="utf-8")


def test_reviewed_chart_renders_static_values_only_on_matching_report(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "site"
    build_site(root, output)
    reports = json.loads((output / "data/reports.json").read_text(encoding="utf-8"))["reports"]
    report_id = reports[0]["id"]
    other_id = reports[1]["id"]
    chart = output / f"data/charts/{report_id}.json"
    chart.parent.mkdir(parents=True, exist_ok=True)
    payload = public_chart()
    payload["report_id"] = report_id
    payload["date"] = reports[0]["date"]
    payload["kind"] = reports[0]["kind"]
    payload["charts"][0]["points"][0]["observation_date"] = reports[0]["date"]
    chart.write_text(json.dumps(rehash(payload), ensure_ascii=False), encoding="utf-8")
    refresh_astro(root, output)
    matching = (output / f"reports/{report_id}/index.html").read_text(encoding="utf-8")
    other = (output / f"reports/{other_id}/index.html").read_text(encoding="utf-8")
    self_contained = ("上涨家数", reports[0]["date"], "https://example.test/source")
    for text in self_contained:
        assert text in matching
    assert "astro-island" in matching
    assert "https://example.test/source" not in other
