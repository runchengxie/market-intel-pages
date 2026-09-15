"""Build a GitHub Pages artifact from the current five-session public snapshot."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


REPORT_SCHEMA = "market_intel_pages.reports.v1"
SUMMARY_SCHEMA = "market_intel_pages.daily_summaries.v1"
PUBLIC_SESSION_COUNT = 5
STATIC_FILES = ("index.html", "app.js", "styles.css")


def _read_index(path: Path, schema: str, key: str) -> tuple[dict, list[dict]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read index: {path}") from exc
    if payload.get("schema_version") != schema or not isinstance(payload.get(key), list):
        raise ValueError(f"unsupported {key} index")
    return payload, payload[key]


def _validate(report_data: dict, reports: list[dict], summaries: list[dict]) -> None:
    by_id = {report.get("id"): report for report in reports}
    for summary in summaries:
        morning = by_id.get(summary.get("morning_report_id"))
        evening = by_id.get(summary.get("evening_report_id"))
        if not morning or not evening:
            raise ValueError("summary source report is missing")
        if morning.get("kind") != "morning" or evening.get("kind") != "evening":
            raise ValueError("summary source report kind is invalid")
        if summary.get("date") != morning.get("date"):
            raise ValueError("summary date must match its morning report")

    sessions = {report.get("date") for report in reports}
    if len(sessions) > PUBLIC_SESSION_COUNT:
        raise ValueError("public report snapshot exceeds five trading dates")


def build_site(root: Path, output: Path, summaries_path: Path | None = None) -> None:
    root = root.resolve()
    output = output.resolve()
    summaries_path = (summaries_path or root / "data/daily_summaries.json").resolve()
    report_data, reports = _read_index(root / "data/reports.json", REPORT_SCHEMA, "reports")
    summary_data, summaries = _read_index(summaries_path, SUMMARY_SCHEMA, "summaries")
    _validate(report_data, reports, summaries)

    if output == root or output.is_relative_to(root):
        raise ValueError("build output must be outside the repository")
    if output.exists():
        shutil.rmtree(output)
    (output / "data").mkdir(parents=True)
    (output / "reports").mkdir()
    for filename in STATIC_FILES:
        shutil.copy2(root / filename, output / filename)
    shutil.copy2(root / "data/reports.json", output / "data/reports.json")
    shutil.copy2(summaries_path, output / "data/daily_summaries.json")

    for report in reports:
        source_url = report.get("source_url")
        source = (root / source_url).resolve()
        if not source.is_relative_to((root / "reports").resolve()) or not source.is_file():
            raise ValueError(f"report Markdown is missing or unsafe: {source_url}")
        destination = output / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--output", type=Path, required=True, help="Pages artifact output directory")
    parser.add_argument("--summaries", type=Path, help="summary index override")
    args = parser.parse_args()
    build_site(args.root, args.output, args.summaries)
    print(f"Built public site at {args.output}")


if __name__ == "__main__":
    main()
