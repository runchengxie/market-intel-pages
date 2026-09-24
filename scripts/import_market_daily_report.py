"""Import a validated platform daily report into the public Pages tree."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_PREFIX = "1."
REQUIRED_FIELDS = {"schema_version", "as_of", "generated_at", "run_id", "facts", "claims", "source_status"}
FACT_LABELS = {
    "treasury.2y.change_bp": ("2 年期美债收益率日变动", "bp"),
    "treasury.5y.change_bp": ("5 年期美债收益率日变动", "bp"),
    "treasury.10y.change_bp": ("10 年期美债收益率日变动", "bp"),
    "treasury.30y.change_bp": ("30 年期美债收益率日变动", "bp"),
    "macro.cpi_yoy": ("CPI 同比", "%"),
    "macro.pce_yoy": ("PCE 同比", "%"),
    "macro.unemployment_rate": ("失业率", "%"),
    "macro.payroll_change_thousands": ("非农就业月变动", "千人"),
}
MISSING_LABELS = {
    "quotes": "指数行情",
    "research": "研究解释",
    "fred": "部分 FRED 数据",
    "rates_lag": "当日收益率",
}


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("daily report must be an object")
    missing = sorted(REQUIRED_FIELDS.difference(payload))
    if missing:
        raise ValueError(f"daily report missing fields: {', '.join(missing)}")
    if not str(payload["schema_version"]).startswith(SCHEMA_PREFIX):
        raise ValueError("unsupported daily report schema")
    if payload.get("quality_summary", {}).get("status") == "fixture":
        raise ValueError("fixture daily report cannot be published")
    serialized = json.dumps(payload, ensure_ascii=False)
    if "API_KEY" in serialized or "auth.json" in serialized or "Bearer " in serialized:
        raise ValueError("credentials detected in daily report")
    for claim in payload["claims"]:
        if not claim.get("evidence_ids") or not claim.get("sources"):
            raise ValueError("every daily report claim needs evidence and sources")
    if any(fact.get("id") in FACT_LABELS for fact in payload["facts"]):
        market_date = (
            datetime.fromisoformat(payload["as_of"])
            .astimezone(ZoneInfo("America/New_York"))
            .date()
            .isoformat()
        )
        if payload["run_id"] != f"daily-{market_date}":
            raise ValueError("daily report market date mismatch")
    return payload


def _date(payload: dict[str, Any]) -> str:
    run_id = str(payload["run_id"])
    if re.fullmatch(r"daily-\d{4}-\d{2}-\d{2}", run_id):
        return run_id.removeprefix("daily-")
    return str(payload["as_of"])[:10]


def _macro_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for fact in payload["facts"]:
        label = FACT_LABELS.get(fact.get("id"))
        if label is None:
            continue
        value = fact.get("value")
        url = str(fact.get("source_url") or "")
        observed = str(fact.get("observation_date") or "")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not re.fullmatch(r"https://fred\.stlouisfed\.org/series/[A-Z0-9]+", url)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed)
        ):
            raise ValueError(f"invalid sourced macro fact: {fact.get('id')}")
        lines.append(
            f"- {label[0]}：{value:.2f}{'' if label[1] == '%' else ' '}{label[1]}"
            f"（观测日 {observed}；[FRED]({url})）"
        )
    if not lines:
        return []
    return ["## 美国宏观与利率", "", *lines, ""]


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 美股市场日报（{_date(payload)}）",
        "",
        f"数据状态：{payload.get('quality_summary', {}).get('status', 'unknown')}",
        "",
    ]
    lines.extend(_macro_lines(payload))
    gaps = [MISSING_LABELS[item] for item in payload.get("missing_sources", []) if item in MISSING_LABELS]
    if gaps:
        lines.extend([f"尚缺：{'、'.join(gaps)}。", ""])
    lines.extend(["## 研究解释", ""])
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
