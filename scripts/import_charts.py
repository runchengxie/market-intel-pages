"""Preview or atomically import one independently reviewed public chart file."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

try:
    from .chart_contract import validate_public_chart
except ImportError:
    from chart_contract import validate_public_chart


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def import_charts(root: Path, source: Path, archive: Path, *, apply: bool = False) -> dict:
    """Require a public manifest and an indexed report; never promote candidates."""
    root, source, archive = root.resolve(), source.resolve(), archive.resolve()
    if archive.is_relative_to(root) or root.is_relative_to(archive):
        raise ValueError("chart archive must be outside public repository")
    payload = validate_public_chart(json.loads(source.read_text(encoding="utf-8")))
    report_id = payload["report_id"]
    index = json.loads((root / "data/reports.json").read_text(encoding="utf-8"))
    if index.get("schema_version") != "market_intel_pages.reports.v1" or not isinstance(
        index.get("reports"), list
    ):
        raise ValueError("invalid report index")
    if report_id not in {item.get("id") for item in index["reports"] if isinstance(item, dict)}:
        raise ValueError("chart identity is not in the public report index")
    destination = root / "data" / "charts" / f"{report_id}.json"
    old = destination.read_bytes() if destination.is_file() else None
    data = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    changed = int(old != data)
    result = {"changed": changed, "report_id": report_id, "applied": False}
    if not apply or not changed:
        return result
    if old is not None:
        old_payload = validate_public_chart(json.loads(old))
        old_hash = old_payload["content_sha256"]
        archive_path = archive / "chart_revisions" / report_id / f"{old_hash}.json"
        if not archive_path.exists():
            _write_atomic(archive_path, old)
    _write_atomic(destination, data)
    return {**result, "applied": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(import_charts(args.root, args.source, args.archive, apply=args.apply), ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
