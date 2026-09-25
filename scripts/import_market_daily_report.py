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
    "treasury.2y.level_percent": ("2 年期美债收益率水平", "%"),
    "treasury.5y.level_percent": ("5 年期美债收益率水平", "%"),
    "treasury.10y.level_percent": ("10 年期美债收益率水平", "%"),
    "treasury.30y.level_percent": ("30 年期美债收益率水平", "%"),
    "cross_asset.brent.close": ("布伦特期货收盘", "美元/桶"),
    "cross_asset.brent.change_percent": ("布伦特日涨跌", "%"),
    "cross_asset.gold.close": ("COMEX 黄金期货收盘", "美元/金衡盎司"),
    "cross_asset.gold.change_percent": ("黄金日涨跌", "%"),
    "cross_asset.silver.close": ("COMEX 白银期货收盘", "美元/金衡盎司"),
    "cross_asset.silver.change_percent": ("白银日涨跌", "%"),
    "cross_asset.bitcoin.close": ("CME 比特币期货收盘", "美元/BTC"),
    "cross_asset.bitcoin.change_percent": ("比特币期货日涨跌", "%"),
    "macro.cpi_yoy": ("CPI 同比", "%"),
    "macro.pce_yoy": ("PCE 同比", "%"),
    "macro.unemployment_rate": ("失业率", "%"),
    "macro.payroll_change_thousands": ("非农就业月变动", "千人"),
}
FRED_URL = r"https://fred\.stlouisfed\.org/series/[A-Z0-9]+"
TREASURY_URL = r"https://home\.treasury\.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates\.csv/all/\d{6}\?_format=csv&field_tdr_date_value_month=\d{6}&page=&type=daily_treasury_yield_curve"
YAHOO_URLS = {
    "brent": r"https://finance\.yahoo\.com/quote/BZ%3DF/history/",
    "gold": r"https://finance\.yahoo\.com/quote/GC%3DF/history/",
    "silver": r"https://finance\.yahoo\.com/quote/SI%3DF/history/",
    "bitcoin": r"https://finance\.yahoo\.com/quote/BTC%3DF/history/",
}
MISSING_LABELS = {
    "quotes": "指数行情",
    "research": "研究解释",
    "fred": "部分 FRED 数据",
    "rates_lag": "美债收益率当日变动",
    "cross_asset": "布伦特、金银或比特币行情",
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
RESEARCH_SECTION_TITLES = {
    "market": "美股市场表现",
    "cross_asset": "跨资产行情",
    "drivers": "市场驱动因素",
    "macro": "经济数据与美联储动态",
    "company_news": "公司新闻",
    "movers": "主要上涨与下跌个股",
}


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


def _valid_market_fact(fact: dict[str, Any], report_date: str) -> bool:
    fact_id = str(fact.get("id") or "")
    observed = fact.get("observation_date")
    source_url = str(fact.get("source_url") or "")
    unit = fact.get("unit")
    if fact_id.startswith("index."):
        return (
            fact.get("quality") == "reviewed"
            and unit == "percent"
            and observed == report_date
            and source_url.startswith("https://")
        )
    if fact_id.startswith("treasury."):
        is_level = fact_id.endswith(".level_percent")
        expected_unit = "percent" if is_level else "basis_points"
        expected_metric = "yield_level" if is_level else "yield_change"
        source_valid = bool(re.fullmatch(TREASURY_URL, source_url)) or bool(
            re.fullmatch(FRED_URL, source_url)
        )
        return source_valid and unit == expected_unit and fact.get("metric") == expected_metric
    if fact_id.startswith("cross_asset."):
        parts = fact_id.split(".")
        if len(parts) != 3:
            return False
        _, asset, field = parts
        url_pattern = YAHOO_URLS.get(asset)
        is_close = field == "close"
        expected_unit = {
            "brent": "USD/barrel",
            "gold": "USD/troy_ounce",
            "silver": "USD/troy_ounce",
            "bitcoin": "USD/bitcoin",
        }.get(asset)
        expected_metric = (
            ("crypto_futures_close" if asset == "bitcoin" else "commodity_close")
            if is_close
            else "daily_return"
        )
        return (
            url_pattern is not None
            and bool(re.fullmatch(url_pattern, source_url))
            and fact.get("source") == "Yahoo Finance"
            and fact.get("quality") == "ok"
            and observed == report_date
            and unit == (expected_unit if is_close else "percent")
            and fact.get("metric") == expected_metric
        )
    if fact_id.startswith("macro."):
        return bool(re.fullmatch(FRED_URL, source_url))
    return False


def _valid_sourced_fact_date(payload: dict[str, Any]) -> bool:
    if not any(fact.get("id") in FACT_LABELS for fact in payload["facts"]):
        return True
    if not _valid_report_time(payload):
        return False
    report_date = str(payload["run_id"]).removeprefix("daily-")
    report_date = str(payload["run_id"]).removeprefix("daily-")
    known_facts = [fact for fact in payload["facts"] if fact.get("id") in FACT_LABELS]
    if not all(_valid_market_fact(fact, report_date) for fact in known_facts):
        return False
    facts_by_id = {fact["id"]: fact for fact in known_facts}
    for tenor in ("2y", "5y", "10y", "30y"):
        level = facts_by_id.get(f"treasury.{tenor}.level_percent")
        change = facts_by_id.get(f"treasury.{tenor}.change_bp")
        if (
            level
            and change
            and any(level.get(key) != change.get(key) for key in ("observation_date", "source", "source_url"))
        ):
            return False
    for asset in YAHOO_URLS:
        close = facts_by_id.get(f"cross_asset.{asset}.close")
        change = facts_by_id.get(f"cross_asset.{asset}.change_percent")
        if bool(close) != bool(change):
            return False
    return True


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
        "report_formats": ["md", "txt"],
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
            for key in ("rates", "macro", "quotes", "research", "cross_asset")
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


def _fact_category(fact_id: str) -> str:
    for prefix, category in (
        ("index.", "market"),
        ("treasury.", "rates"),
        ("cross_asset.", "cross_asset"),
        ("macro.", "macro"),
    ):
        if fact_id.startswith(prefix):
            return category
    return ""


def _markdown_source(fact: dict[str, Any]) -> str:
    fact_id = str(fact["id"])
    url = str(fact["source_url"])
    if fact_id.startswith("index."):
        name = "核实报道"
    elif fact_id.startswith("cross_asset."):
        name = "Yahoo Finance"
    elif url.startswith("https://home.treasury.gov/"):
        name = "美国财政部"
    else:
        name = "FRED"
    return f"[{name}]({url})"


def _market_table(facts: list[dict[str, Any]]) -> list[str]:
    lines = ["| 指数 | 收盘涨跌 | 观测日 | 来源 |", "|---|---:|---|---|"]
    for fact in facts:
        label = FACT_LABELS[fact["id"]][0].removesuffix("日涨跌").strip()
        lines.append(
            f"| {label} | {float(fact['value']):+.2f}% | {fact['observation_date']} | {_markdown_source(fact)} |"
        )
    return lines


def _rates_table(facts: list[dict[str, Any]]) -> list[str]:
    lines = ["| 美债期限 | 收益率水平 | 日变动 | 观测日 | 来源 |", "|---|---:|---:|---|---|"]
    names = {"2y": "2 年期", "5y": "5 年期", "10y": "10 年期", "30y": "30 年期"}
    for fact in facts:
        _, tenor, metric = fact["id"].split(".")
        if metric == "level_percent":
            continue
        level = next((row for row in facts if row["id"] == f"treasury.{tenor}.level_percent"), None)
        level_text = f"{float(level['value']):.2f}%" if level else "—"
        lines.append(
            f"| {names[tenor]} | {level_text} | {float(fact['value']):+.2f} bp | "
            f"{fact['observation_date']} | {_markdown_source(fact)} |"
        )
    return lines


def _cross_asset_table(facts: list[dict[str, Any]]) -> list[str]:
    lines = ["| 品种 | 期货价格 | 日涨跌 | 观测日 | 来源 |", "|---|---:|---:|---|---|"]
    for fact in facts:
        if not fact["id"].endswith(".close"):
            continue
        _, asset, _ = fact["id"].split(".")
        change = next((row for row in facts if row["id"] == f"cross_asset.{asset}.change_percent"), None)
        if change is None:
            continue
        label = FACT_LABELS[fact["id"]][0].removesuffix("收盘")
        unit = FACT_LABELS[fact["id"]][1]
        lines.append(
            f"| {label} | {float(fact['value']):,.2f} {unit} | {float(change['value']):+.2f}% | "
            f"{fact['observation_date']} | {_markdown_source(fact)} |"
        )
    return lines


def _macro_table(facts: list[dict[str, Any]]) -> list[str]:
    lines = ["| 数据 | 数值 | 观测日 | 来源 |", "|---|---:|---|---|"]
    for fact in facts:
        label, unit = FACT_LABELS[fact["id"]]
        lines.append(
            f"| {label} | {float(fact['value']):.2f}{unit} | {fact['observation_date']} | "
            f"{_markdown_source(fact)} |"
        )
    return lines


def _markdown_fact_lines(payload: dict[str, Any], section: str) -> list[str]:
    grouped = []
    for fact in payload["facts"]:
        fact_id = str(fact.get("id") or "")
        if _fact_category(fact_id) != section or fact_id not in FACT_LABELS:
            continue
        value = fact.get("value")
        observed = str(fact.get("observation_date") or "")
        is_valid = (
            not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(value)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", observed)
            and _valid_market_fact(fact, _date(payload))
        )
        if not is_valid:
            raise ValueError(f"invalid sourced market fact: {fact_id}")
        grouped.append(fact)
    if not grouped:
        return []
    renderers = {
        "market": _market_table,
        "rates": _rates_table,
        "cross_asset": _cross_asset_table,
        "macro": _macro_table,
    }
    return renderers[section](grouped)


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# 美股市场日报（{_date(payload)}）",
        "",
        f"数据状态：{payload.get('quality_summary', {}).get('status', 'unknown')}",
        f"报告生成时间：{payload['as_of']}（美东报告日 {_date(payload)}）",
        "",
    ]
    cutoff = payload.get("quality_summary", {}).get("reviewed_source_cutoff")
    if cutoff:
        lines[4:4] = [f"新闻资料截止：{cutoff}。", ""]
    gaps = [MISSING_LABELS[item] for item in payload.get("missing_sources", []) if item in MISSING_LABELS]
    if gaps:
        lines.extend([f"尚缺：{'、'.join(gaps)}。", ""])
    grouped = _group_claims(payload)
    report_sections = (
        ("market", "美股市场表现"),
        ("rates", "美债收益率"),
        ("cross_asset", "布伦特、金银与比特币"),
        ("drivers", "市场驱动因素"),
        ("macro", "经济数据与美联储动态"),
        ("company_news", "公司新闻"),
        ("movers", "主要个股"),
    )
    for key, title in report_sections:
        lines.extend([f"## {title}", ""])
        facts = _markdown_fact_lines(payload, key)
        lines.extend(facts)
        for claim in grouped.get(key, []):
            evidence = ", ".join(f"`{item}`" for item in claim["evidence_ids"])
            sources = "、".join(
                f"[来源{index}]({url})" for index, url in enumerate(claim["sources"], start=1)
            )
            lines.extend([f"- {claim['claim']}", f"  - 证据：{evidence}", f"  - {sources}"])
        if not facts and not grouped.get(key, []):
            lines.append("暂无经核实内容。")
        lines.append("")
    if grouped["other"]:
        lines.extend(["## 其他已核实内容", ""])
        for claim in grouped["other"]:
            evidence = ", ".join(f"`{item}`" for item in claim["evidence_ids"])
            sources = "、".join(
                f"[来源{index}]({url})" for index, url in enumerate(claim["sources"], start=1)
            )
            lines.extend([f"- {claim['claim']}", f"  - 证据：{evidence}", f"  - {sources}"])
    lines.append("")
    return "\n".join(lines)


def _text_fact_lines(payload: dict[str, Any], prefix: str) -> list[str]:
    facts = {fact["id"]: fact for fact in payload["facts"] if fact.get("id") in FACT_LABELS}
    lines = []
    for fact_id, (label, unit) in FACT_LABELS.items():
        if not fact_id.startswith(prefix) or fact_id not in facts:
            continue
        fact = facts[fact_id]
        signed = fact_id.startswith("index.") or fact_id.endswith((".change_bp", ".change_percent"))
        value = f"{fact['value']:+.2f}" if signed else f"{fact['value']:.2f}"
        suffix = unit if unit == "%" else f" {unit}"
        lines.extend(
            [
                f"- {label}：{value}{suffix}（观测日 {fact['observation_date']}）",
                f"  来源：{fact['source_url']}",
            ]
        )
    return lines


def _group_claims(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {key: [] for key in RESEARCH_SECTION_TITLES}
    groups["other"] = []
    section_ids = {
        section.get("key"): set(section.get("claims", []))
        for section in payload.get("sections", [])
        if isinstance(section, dict) and isinstance(section.get("claims"), list)
    }
    for claim in payload["claims"]:
        key = next(
            (
                key
                for key in RESEARCH_SECTION_TITLES
                if section_ids.get(key, set()).intersection(claim["evidence_ids"])
            ),
            "other",
        )
        groups[key].append(claim)
    return groups


def _text_claim_lines(claims: list[dict[str, Any]]) -> list[str]:
    if not claims:
        return ["- 暂无经核实内容。"]
    lines = []
    for index, claim in enumerate(claims, start=1):
        lines.extend([f"{index}、{claim['claim']}", *(f"   来源：{url}" for url in claim["sources"])])
    return lines


def _text_report(payload: dict[str, Any]) -> str:
    report_date = _date(payload)
    grouped = _group_claims(payload)
    market_facts = _text_fact_lines(payload, "index.")
    treasury_facts = _text_fact_lines(payload, "treasury.")
    macro_facts = _text_fact_lines(payload, "macro.")
    cross_asset_facts = _text_fact_lines(payload, "cross_asset.")
    lines = [
        f"美股市场日报｜{report_date} 美东报告日",
        f"报告生成时间：{payload['as_of']}；逐项显示原始观测日。",
        "",
        "一、美股市场表现",
        *(market_facts or ["- 暂无经核实指数行情。"]),
        *(_text_claim_lines(grouped["market"]) if grouped["market"] else []),
        "",
        "二、美债、布伦特、金银与比特币",
        *(treasury_facts or ["- 暂无经核实的美债收益率水平或日变动。"]),
        *(cross_asset_facts or ["- 暂无经核实的跨资产行情。"]),
        "",
        "三、市场驱动因素",
        *_text_claim_lines(grouped["drivers"]),
        "",
        "四、经济数据与美联储动态",
        *(macro_facts or ["- 暂无经核实利率与宏观数据。"]),
        *(_text_claim_lines(grouped["macro"]) if grouped["macro"] else []),
        "",
        "五、公司新闻",
        *_text_claim_lines(grouped["company_news"]),
        "",
        "六、主要上涨与下跌个股",
        *_text_claim_lines(grouped["movers"]),
        "",
    ]
    cutoff = payload.get("quality_summary", {}).get("reviewed_source_cutoff")
    if cutoff:
        lines[2:2] = [f"新闻资料截止：{cutoff}。"]
    if grouped["other"]:
        lines.extend(["六、其他已核实内容", *_text_claim_lines(grouped["other"])])
    gaps = [MISSING_LABELS[item] for item in payload.get("missing_sources", []) if item in MISSING_LABELS]
    if gaps:
        lines.extend(["", f"尚缺：{'、'.join(gaps)}。"])
    lines.extend(["", "风险提示：市场有风险，投资需谨慎。", ""])
    return "\n".join(lines)


def import_report(source: Path, root: Path, manifest_path: Path) -> str:
    manifest = _public_manifest(source, manifest_path)
    payload = _public_payload(_read(source), manifest)
    report_date = _date(payload)
    data_path = root / "data/market_daily_report.json"
    report_path = root / f"reports/{report_date}-market-daily.md"
    text_path = root / f"reports/{report_date}-market-daily.txt"
    data_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(_markdown(payload), encoding="utf-8")
    text_path.write_text(_text_report(payload), encoding="utf-8")
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
