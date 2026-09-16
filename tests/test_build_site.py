import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_site import build_site
from scripts.sync_public_snapshot import sync_snapshot


REPORT_SCHEMA = "market_intel_pages.reports.v1"
SUMMARY_SCHEMA = "market_intel_pages.daily_summaries.v1"


def create_site(root: Path, session_count: int = 6) -> None:
    (root / "data").mkdir(parents=True)
    (root / "reports").mkdir()
    for name in ("index.html", "app.js", "styles.css", "summary-utils.js"):
        (root / name).write_text(name, encoding="utf-8")

    reports = []
    for day in range(1, session_count + 1):
        date = f"2026-09-{day:02d}"
        for kind in ("morning", "evening"):
            report_id = f"{date}-{kind}"
            source_url = f"reports/{report_id}.md"
            reports.append({
                "id": report_id,
                "date": date,
                "kind": kind,
                "title": report_id,
                "summary": "sample",
                "sections": [],
                "source_url": source_url,
            })
            (root / source_url).write_text(f"# {report_id}\n", encoding="utf-8")

    (root / "data/reports.json").write_text(json.dumps({
        "schema_version": REPORT_SCHEMA,
        "generated_at": "2026-09-16T08:00:00+08:00",
        "reports": reports,
    }), encoding="utf-8")
    (root / "data/daily_summaries.json").write_text(json.dumps({
        "schema_version": SUMMARY_SCHEMA,
        "summaries": [],
    }), encoding="utf-8")


class BuildSiteTests(unittest.TestCase):
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
            summaries.append({
                "date": "2026-09-06",
                "text": f"note from {evening_id}",
                "morning_report_id": "2026-09-06-morning",
                "evening_report_id": evening_id,
                "generated_at": "2026-09-07T07:00:00+08:00",
                "model": "test",
                "prompt_version": "daily-note-v1",
            })
        (self.root / "data/daily_summaries.json").write_text(json.dumps({
            "schema_version": SUMMARY_SCHEMA,
            "summaries": summaries,
        }), encoding="utf-8")

        sync_snapshot(self.root, self.archive)

        local = json.loads((self.archive / "data/daily_summaries.json").read_text())
        pairs = {(row["morning_report_id"], row["evening_report_id"]) for row in local["summaries"]}
        self.assertEqual({
            ("2026-09-06-morning", "2026-09-05-evening"),
            ("2026-09-06-morning", "2026-09-06-evening"),
        }, pairs)

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
        self.assertEqual("market_intel_pages.daily_summaries.v1", json.loads(
            (self.output / "data/daily_summaries.json").read_text()
        )["schema_version"])

    def test_build_rejects_summary_with_unknown_source(self) -> None:
        (self.root / "data/daily_summaries.json").write_text(json.dumps({
            "schema_version": SUMMARY_SCHEMA,
            "summaries": [{
                "date": "2026-09-06",
                "text": "sample",
                "morning_report_id": "missing-morning",
                "evening_report_id": "2026-09-06-evening",
                "generated_at": "2026-09-07T07:00:00+08:00",
                "model": "test",
                "prompt_version": "daily-note-v1",
            }],
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source report"):
            build_site(self.root, self.output, self.root / "data/daily_summaries.json")


if __name__ == "__main__":
    unittest.main()
