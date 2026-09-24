"""Import a validated platform daily report into the public Pages tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SCHEMA_PREFIX = "1."
DATE_FIELDS = {"as_of", "generated_at", "source_time", "retrieved_at"}
REQUIRED_FIELDS = {"schema_version", "as_of", "generated_at", "run_id", "facts", "claims", "source_status"}
FACT_LABELS = {
    "index.spx.change_percent": ("标普 500 日涨跌", "%"),
    "index.dow.change_percent": ("道指日涨跌", "%"),
    "index.nasdaq.change_percent": ("纳指日涨跌", "%"),
    "index.russell2000.change_percent": ("罗素 2000 日涨跌", "%"),
    "treasury.2y.change_bp": ("2 年期美债收益率日变动", "bp"),
    "treasury.5y.change_bp": ("5 年期美债收益率日变动", "bp"),
    "treasury.10y.change_bp": ("10 年期美债收益率日变动", "bp"),
    "treasury.30y.change_bp": ("30 年期美债收益率日变动", "bp"),
    "macro.cpi_yoy": ("CPI 同比", "%"),
    "macro.pce_yoy": ("PCE 同比", "%"),
    "macro.unemployment_rate": ("失业率", "%"),
    "macro.payroll_change_thousands": ("非农就业月变动", "千人"),
}
FRED_URL = r"https://fred\.stlouisfed\.org/series/[A-Z0-9]+"
TREASURY_URL = r"https://home\.treasury\.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates\.csv/all/\d{6}\?_format=csv&field_tdr_date_value_month=\d{6}&page=&type=daily_treasury_yield_curve"
MISSING_LABELS = {
    "quotes": "指数行情",
    "research": "研究解释",
    "fred": "部分 FRED 数据",
    "rates_lag": "美债收益率当日变动",
}
PUBLIC_FACT_FIELDS = (
    "id",
    "metric",
    "instrument",
    "value",
    "previous",
    "change",
    "unit",
    "source",
    "source_url",
    "source_time",
    "retrieved_at",
    "quality",
    "observation_date",
)
PUBLIC_EVENT_FIELDS = ("id",)
PUBLIC_CLAIM_FIELDS = (
    "claim",
    "evidence_ids",
    "sources",
    "confidence",
    "status",
    "provider",
)
PUBLIC_SECTION_FIELDS = ("key", "title", "facts", "claims")


def _valid_report_time(payload: dict[str, Any]) -> bool:
    market_time = datetime.fromisoformat(payload["as_of"]).astimezone(ZoneInfo("America/New_York"))
    report_date = date.fromisoformat(str(payload["run_id"]).removeprefix("daily-"))
    return market_time.date() == report_date or (
        market_time.date() == report_date + timedelta(days=1) and market_time.time() < time(9, 30)
    )


def _valid_claims(claims: list[dict[str, Any]]) -> bool:
    return all(
        claim.get("evidence_ids")
        and claim.get("sources")
        and all(str(url).startswith("https://") for url in claim["sources"])
        for claim in claims
    )


def _normalize(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        return {name: _normalize(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item, key) for item in value]
    if isinstance(value, str) and key in DATE_FIELDS:
        return datetime.fromisoformat(value)
    return value


def _valid_content_hash(payload: dict[str, Any]) -> bool:
    content = dict(payload)
    claimed = content.get("content_hash")
    content["content_hash"] = None
    digest = hashlib.sha256(
        json.dumps(_normalize(content), default=str, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return claimed == digest


def _unique_evidence_ids(payload: dict[str, Any]) -> bool:
    return all(
        len(identifiers) == len(set(identifiers))
        for identifiers in (
            [row.get("id") for row in payload["facts"]],
            [row.get("id") for row in payload.get("events", [])],
        )
    )


def _valid_sourced_fact_date(payload: dict[str, Any]) -> bool:
    return not any(fact.get("id") in FACT_LABELS for fact in payload["facts"]) or _valid_report_time(payload)


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
    if not _valid_content_hash(payload):
        raise ValueError("daily report content hash mismatch")
    if not _unique_evidence_ids(payload):
        raise ValueError("duplicate daily report evidence IDs")
    serialized = json.dumps(payload, ensure_ascii=False)
    if "API_KEY" in serialized or "auth.json" in serialized or "Bearer " in serialized:
        raise ValueError("credentials detected in daily report")
    if not _valid_claims(payload["claims"]):
        raise ValueError("every daily report claim needs evidence and HTTPS sources")
    if not _valid_sourced_fact_date(payload):
        raise ValueError("daily report market date mismatch")
    return payload


def _public_manifest(source: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = json.loads(source.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != "1.0"
        or manifest.get("publication") != "public"
        or manifest.get("report_file") != "daily_report.json"
        or manifest.get("report_sha256") != hashlib.sha256(source.read_bytes()).hexdigest()
        or manifest.get("run_id") != payload.get("run_id")
        or manifest.get("content_hash") != payload.get("content_hash")
    ):
        raise ValueError("public manifest does not match daily report")
    return manifest


def _select(row: dict[str, Any], names: tuple[str, ...]) -> dict[str, Any]:
    return {name: row[name] for name in names if name in row}


def _public_payload(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    facts = [_select(fact, PUBLIC_FACT_FIELDS) for fact in payload["facts"] if fact.get("id") in FACT_LABELS]
    claims = [_select(claim, PUBLIC_CLAIM_FIELDS) for claim in payload["claims"]]
    evidence_ids = {item for claim in claims for item in claim.get("evidence_ids", [])}
    events = [
        _select(event, PUBLIC_EVENT_FIELDS)
        for event in payload.get("events", [])
        if event.get("id") in evidence_ids
    ]
    return {
        "schema_version": payload["schema_version"],
        "publication": "public",
        "as_of": payload["as_of"],
        "generated_at": payload["generated_at"],
        "run_id": payload["run_id"],
        "sections": [_select(section, PUBLIC_SECTION_FIELDS) for section in payload.get("sections", [])],
        "facts": facts,
        "events": events,
        "claims": claims,
        "missing_sources": [item for item in payload.get("missing_sources", []) if item in MISSING_LABELS],
        "quality_summary": _select(
            payload.get("quality_summary", {}),
            ("status", "revision", "reviewed_source_cutoff"),
        ),
        "source_status": {
            key: _select(payload.get("source_status", {}).get(key, {}), ("quality", "reason"))
            for key in ("rates", "macro", "quotes", "research")
            if key in payload.get("source_status", {})
        },
        "content_hash": payload.get("content_hash"),
        "source_report_sha256": manifest["report_sha256"],
    }


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
        fact_id = str(fact.get("id") or "")
        if fact_id.startswith("index."):
            valid_source = (
                url.startswith("https://")
                and fact.get("quality") == "reviewed"
                and observed == _date(payload)
            )
            source_name = "核实报道"
        elif fact_id.startswith("treasury.") and re.fullmatch(TREASURY_URL, url):
            valid_source = True
            source_name = "美国财政部"
        else:
            valid_source = bool(re.fullmatch(FRED_URL, url))
            source_name = "FRED"
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not valid_source
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed)
        ):
            raise ValueError(f"invalid sourced macro fact: {fact.get('id')}")
        lines.append(
            f"- {label[0]}：{value:.2f}{'' if label[1] == '%' else ' '}{label[1]}"
            f"（观测日 {observed}；[{source_name}]({url})）"
        )
    if not lines:
        return []
    return ["## 美国市场、宏观与利率", "", *lines, ""]


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 美股市场日报（{_date(payload)}）",
        "",
        f"数据状态：{payload.get('quality_summary', {}).get('status', 'unknown')}",
        f"资料核实截至：{payload['as_of']}（美东报告日 {_date(payload)}）",
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


def import_report(source: Path, root: Path, manifest_path: Path) -> str:
    manifest = _public_manifest(source, manifest_path)
    payload = _public_payload(_read(source), manifest)
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
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    print(import_report(args.input, args.root, args.manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
