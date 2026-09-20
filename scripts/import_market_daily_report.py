"""Import a validated platform daily report into the public Pages tree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_PREFIX = "1."
REQUIRED_FIELDS = {"schema_version", "as_of", "generated_at", "run_id", "facts", "claims", "source_status"}


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("daily report must be an object")
    missing = sorted(REQUIRED_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"daily report missing fields: {', '.join(missing)}")
    if not str(payload["schema_version"]).startswith(SCHEMA_PREFIX):
        raise ValueError("unsupported daily report schema")
    serialized = json.dumps(payload, ensure_ascii=False)
    if "API_KEY" in serialized or "auth.json" in serialized or "Bearer " in serialized:
        raise ValueError("credentials detected in daily report")
    for claim in payload["claims"]:
        if not claim.get("evidence_ids") or not claim.get("sources"):
            raise ValueError("every daily report claim needs evidence and sources")
    return payload


def _date(payload: dict[str, Any]) -> str:
    return str(payload["as_of"])[:10]


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 美股市场日报（{_date(payload)}）",
        "",
        f"数据状态：{payload.get('quality_summary', {}).get('status', 'unknown')}",
        "",
    ]
    for claim in payload["claims"]:
        evidence = ", ".join(f"`{item}`" for item in claim["evidence_ids"])
        lines.extend(
            [f"- {claim['claim']}", f"  - 证据：{evidence}", f"  - 来源：{', '.join(claim['sources'])}"]
        )
    if not payload["claims"]:
        lines.append("暂无已校验的研究结论。")
    lines.append("")
    return "\n".join(lines)


def import_report(source: Path, root: Path) -> str:
    payload = _read(source)
    report_date = _date(payload)
    data_path = root / "data/market_daily_report.json"
    report_path = root / f"reports/{report_date}-market-daily.md"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    return report_date


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(import_report(args.input, args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
