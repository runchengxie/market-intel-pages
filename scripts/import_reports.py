"""Import an explicitly public Markdown manifest. Preview by default; never send messages."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from .generate_daily_summary import CHINA_TZ, report_generated_at
    from .generate_insights import archive_once, write_json
    from .sync_public_snapshot import sync_snapshot, _safe_report_path
except ImportError:
    from generate_daily_summary import CHINA_TZ, report_generated_at
    from generate_insights import archive_once, write_json
    from sync_public_snapshot import sync_snapshot, _safe_report_path


def parse_markdown(text: str, date: str, kind: str) -> dict:
    datetime.strptime(date, "%Y-%m-%d")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or kind not in ("morning", "evening"):
        raise ValueError("invalid report identity")
    title, sections, section = "", [], {"title": "报告信息", "paragraphs": []}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("# ") and not title:
            title = line[2:].strip()
        elif re.match(r"#{2,6} ", line):
            if section["paragraphs"]:
                sections.append(section)
            section = {"title": re.sub(r"^#{2,6} ", "", line), "paragraphs": []}
        else:
            section["paragraphs"].append(line)
    if section["paragraphs"]:
        sections.append(section)
    report_id = f"{date}-{kind}"
    row = {"id": report_id, "date": date, "kind": kind, "title": title, "sections": sections,
           "source_url": f"reports/{report_id}.md"}
    generated = report_generated_at(row)
    if not title or generated is None or not sections:
        raise ValueError("Markdown needs title, content and a generation timestamp")
    row["summary"] = f"目标日期 {date}；原报告生成于 {generated:%Y-%m-%d %H:%M}（北京时间）。"
    return row


def import_reports(root: Path, manifest_path: Path, archive_dir: Path, *, apply=False) -> dict:
    root, manifest_path, archive_dir = root.resolve(), manifest_path.resolve(), archive_dir.resolve()
    if archive_dir.is_relative_to(root) or root.is_relative_to(archive_dir):
        raise ValueError("archive and public repository must be separate directories")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema_version") != "market_intel_pages.import.v1"
            or manifest.get("publication") != "public" or not isinstance(manifest.get("reports"), list)
            or not manifest["reports"]):
        raise ValueError("an explicitly public report manifest is required")
    incoming, markdown = {}, {}
    for item in manifest["reports"]:
        path = (manifest_path.parent / item["path"]).resolve()
        if not path.is_relative_to(manifest_path.parent) or path.suffix != ".md" or not path.is_file():
            raise ValueError("unsafe or missing source Markdown")
        text = path.read_text(encoding="utf-8")
        row = parse_markdown(text, item["date"], item["kind"])
        if row["id"] in incoming:
            raise ValueError("duplicate report identity in import")
        incoming[row["id"]], markdown[row["id"]] = row, text
    index = json.loads((root / "data/reports.json").read_text(encoding="utf-8"))
    if index.get("schema_version") != "market_intel_pages.reports.v1":
        raise ValueError("invalid report index")
    existing = {r["id"]: r for r in index["reports"]}
    changed = [key for key, row in incoming.items() if existing.get(key) != row
               or not _safe_report_path(root, row["source_url"]).exists()
               or _safe_report_path(root, row["source_url"]).read_text(encoding="utf-8") != markdown[key]]
    result = {"changed": len(changed), "report_ids": sorted(incoming), "applied": False}
    if not apply or not changed:
        return result
    archive_index = archive_dir / "data/reports.json"
    archived = {r["id"]: r for r in json.loads(archive_index.read_text(encoding="utf-8"))["reports"]} if archive_index.exists() else {}
    # Stage the entire snapshot; source parsing and validation precede public writes.
    with tempfile.TemporaryDirectory(prefix="market-intel-import-") as temporary:
        stage = Path(temporary)
        (stage / "data").mkdir()
        (stage / "reports").mkdir()
        for row in existing.values():
            source = _safe_report_path(root, row["source_url"])
            destination = _safe_report_path(stage, row["source_url"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        for key, row in incoming.items():
            (stage / row["source_url"]).write_text(markdown[key], encoding="utf-8")
        merged = {**existing, **incoming}
        write_json(stage / "data/reports.json", {**index,
                   "generated_at": datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
                   "reports": sorted(merged.values(), key=lambda r: (r["date"], r["id"]))})
        shutil.copy2(root / "data/daily_summaries.json", stage / "data/daily_summaries.json")
        for key in changed:
            for old_index, old_root in ((existing, root), (archived, archive_dir)):
                if key in old_index:
                    archive_once(archive_dir, "report_revisions", {"report": old_index[key],
                                 "markdown": _safe_report_path(old_root, old_index[key]["source_url"]).read_text(encoding="utf-8")})
            archive_once(archive_dir, "report_revisions", {"report": incoming[key], "markdown": markdown[key]})
        sync_snapshot(stage, archive_dir)
        public = json.loads((stage / "data/reports.json").read_text(encoding="utf-8"))
        for row in public["reports"]:
            destination = _safe_report_path(root, row["source_url"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / row["source_url"], destination)
        for name in ("daily_summaries.json", "reports.json"):
            write_json(root / "data" / name, json.loads((stage / "data" / name).read_text(encoding="utf-8")))
        retained = {r["source_url"] for r in public["reports"]}
        for row in existing.values():
            if row["source_url"] not in retained:
                _safe_report_path(root, row["source_url"]).unlink(missing_ok=True)
    return {**result, "applied": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(import_reports(args.root, args.manifest, args.archive_dir, apply=args.apply), ensure_ascii=False))


if __name__ == "__main__":
    main()
