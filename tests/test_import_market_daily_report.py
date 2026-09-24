import hashlib
import json

import pytest

from scripts.import_market_daily_report import _normalize, import_report


def _payload():
    return {
        "schema_version": "1.0",
        "as_of": "2026-09-20T01:00:00+00:00",
        "generated_at": "2026-09-20T01:00:00+00:00",
        "run_id": "daily-2026-09-19",
        "facts": [
            {
                "id": "index.spx.change_percent",
                "value": 0.16,
                "quality": "reviewed",
                "source_url": "https://example.test/report",
                "observation_date": "2026-09-19",
            }
        ],
        "events": [],
        "claims": [
            {
                "claim": "SPX rose",
                "evidence_ids": ["index.spx.change_percent"],
                "sources": ["https://example.test"],
            }
        ],
        "source_status": {"facts": {"quality": "ok"}},
        "quality_summary": {"status": "ok"},
        "content_hash": "ignored-by-fixture",
    }


def _source(tmp_path, payload):
    payload["content_hash"] = None
    payload["content_hash"] = hashlib.sha256(
        json.dumps(_normalize(payload), default=str, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    source = tmp_path / "daily_report.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    manifest = tmp_path / "publication.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "publication": "public",
                "report_file": source.name,
                "report_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "run_id": payload["run_id"],
                "content_hash": payload["content_hash"],
            }
        ),
        encoding="utf-8",
    )
    return source, manifest


def test_import_report_writes_public_json_and_markdown(tmp_path):
    source, manifest = _source(tmp_path, _payload())
    output = tmp_path / "site"
    result = import_report(source, output, manifest)
    assert result == "2026-09-19"
    assert (output / "data/market_daily_report.json").exists()
    assert "SPX rose" in (output / "reports/2026-09-19-market-daily.md").read_text()


def test_import_report_rejects_credentials(tmp_path):
    payload = _payload()
    payload["claims"][0]["claim"] = "API_KEY leaked"
    source, manifest = _source(tmp_path, payload)
    with pytest.raises(ValueError, match="credentials"):
        import_report(source, tmp_path / "site", manifest)


def test_import_report_renders_sourced_macro_facts_for_new_york_date(tmp_path):
    payload = _payload()
    payload.update(
        as_of="2026-09-24T01:00:00+00:00",
        generated_at="2026-09-24T01:00:00+00:00",
        run_id="daily-2026-09-23",
        claims=[],
        facts=[
            {
                "id": "treasury.10y.change_bp",
                "value": -5.0,
                "unit": "basis_points",
                "source_url": "https://fred.stlouisfed.org/series/DGS10",
                "observation_date": "2026-09-23",
            },
            {
                "id": "macro.cpi_yoy",
                "value": 3.4,
                "unit": "percent_yoy",
                "source_url": "https://fred.stlouisfed.org/series/CPIAUCNS",
                "observation_date": "2026-08-01",
            },
        ],
        quality_summary={"status": "degraded"},
        missing_sources=["quotes", "research", "rates_lag"],
    )
    source, manifest = _source(tmp_path, payload)

    assert import_report(source, tmp_path / "site", manifest) == "2026-09-23"
    markdown = (tmp_path / "site/reports/2026-09-23-market-daily.md").read_text()
    assert "10 年期美债收益率日变动：-5.00 bp" in markdown
    assert "CPI 同比：3.40%" in markdown
    assert "观测日 2026-08-01" in markdown
    assert "https://fred.stlouisfed.org/series/CPIAUCNS" in markdown
    assert "指数行情" in markdown
    assert "美债收益率当日变动" in markdown


def test_import_report_rejects_fixture_status(tmp_path):
    payload = _payload()
    payload["quality_summary"]["status"] = "fixture"
    source, manifest = _source(tmp_path, payload)

    with pytest.raises(ValueError, match="fixture"):
        import_report(source, tmp_path / "site", manifest)


def test_import_report_renders_official_rates_and_reviewed_indexes(tmp_path):
    payload = _payload()
    payload.update(
        as_of="2026-09-24T08:30:00+00:00",
        generated_at="2026-09-24T08:30:00+00:00",
        run_id="daily-2026-09-23",
        facts=[
            {
                "id": "treasury.10y.change_bp",
                "value": 15.0,
                "unit": "basis_points",
                "quality": "ok",
                "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve",
                "observation_date": "2026-09-23",
            },
            {
                "id": "index.spx.change_percent",
                "value": -0.8,
                "unit": "percent",
                "quality": "reviewed",
                "source_url": "https://abcnews.com/amp/Business/example",
                "observation_date": "2026-09-23",
            },
        ],
        claims=[
            {
                "claim": "经核实的解释",
                "evidence_ids": ["index.spx.change_percent"],
                "sources": ["https://abcnews.com/amp/Business/example"],
            }
        ],
    )
    source, manifest = _source(tmp_path, payload)
    assert import_report(source, tmp_path / "site", manifest) == "2026-09-23"
    markdown = (tmp_path / "site/reports/2026-09-23-market-daily.md").read_text()
    assert "报告生成时间：2026-09-24T08:30:00+00:00" in markdown
    assert "标普 500 日涨跌：-0.80%" in markdown
    assert "10 年期美债收益率日变动：15.00 bp" in markdown
    assert "美国财政部" in markdown


def test_import_report_writes_source_backed_plain_text_from_public_fields(tmp_path):
    payload = _payload()
    payload.update(
        run_id="daily-2026-09-23",
        as_of="2026-09-24T08:30:00+00:00",
        generated_at="2026-09-24T08:30:00+00:00",
        facts=[
            {
                "id": "index.spx.change_percent",
                "value": -0.8,
                "quality": "reviewed",
                "source_url": "https://abcnews.com/amp/Business/example",
                "observation_date": "2026-09-23",
            },
            {
                "id": "treasury.10y.change_bp",
                "value": 15.0,
                "quality": "ok",
                "source_url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve",
                "observation_date": "2026-09-23",
            },
        ],
        claims=[
            {
                "claim": "报道认为收益率上升带来压力；这不是已证明的唯一因果。",
                "evidence_ids": ["index.spx.change_percent"],
                "sources": ["https://abcnews.com/amp/Business/example"],
            }
        ],
        private_research_draft="private draft must not leak",
    )
    source, manifest = _source(tmp_path, payload)

    assert import_report(source, tmp_path / "site", manifest) == "2026-09-23"
    report = (tmp_path / "site/reports/2026-09-23-market-daily.txt").read_text()
    assert "报告生成时间：2026-09-24T08:30:00+00:00" in report
    assert "一、美股市场表现" in report
    assert "标普 500 日涨跌：-0.80%（观测日 2026-09-23）" in report
    assert "二、市场驱动因素" in report
    assert "三、经济数据与美联储动态" in report
    assert "10 年期美债收益率日变动：+15.00 bp" in report
    assert "暂无经核实内容" not in report.split("三、经济数据与美联储动态")[1].split("四、公司新闻")[0]
    assert "六、其他已核实内容" in report
    assert "报道认为收益率上升带来压力；这不是已证明的唯一因果。" in report
    assert "https://abcnews.com/amp/Business/example" in report
    assert "private draft must not leak" not in report
    assert "市场有风险" in report


def test_plain_text_keeps_reviewed_drivers_and_company_news_in_own_sections(tmp_path):
    payload = _payload()
    payload["facts"].append(
        {
            "id": "macro.cpi_yoy",
            "value": 3.4,
            "source_url": "https://fred.stlouisfed.org/series/CPIAUCNS",
            "observation_date": "2026-08-01",
        }
    )
    payload["events"] = [
        {"id": "reviewed.1", "source_url": "https://example.test/close"},
        {"id": "reviewed.2", "source_url": "https://example.test/company"},
    ]
    payload["claims"] = [
        {
            "claim": "收盘报道将跌势与收益率上涨联系起来。",
            "evidence_ids": ["reviewed.1"],
            "sources": ["https://example.test/close"],
        },
        {
            "claim": "公司公告披露新的季度收入。",
            "evidence_ids": ["reviewed.2"],
            "sources": ["https://example.test/company"],
        },
    ]
    payload["sections"] = [
        {"key": "drivers", "title": "市场驱动因素", "claims": ["reviewed.1"], "facts": []},
        {"key": "company_news", "title": "公司新闻", "claims": ["reviewed.2"], "facts": []},
    ]
    source, manifest = _source(tmp_path, payload)
    import_report(source, tmp_path / "site", manifest)

    report = (tmp_path / "site/reports/2026-09-19-market-daily.txt").read_text()
    assert "二、市场驱动因素" in report
    assert "四、公司新闻" in report
    assert report.index("二、市场驱动因素") < report.index("收盘报道将跌势")
    assert report.index("四、公司新闻") < report.index("公司公告披露")
    assert report.count("收盘报道将跌势") == 1
    assert report.count("公司公告披露") == 1

    markdown = (tmp_path / "site/reports/2026-09-19-market-daily.md").read_text()
    headings = [
        f"## {title}"
        for title in (
            "美股市场表现",
            "市场驱动因素",
            "经济数据与美联储动态",
            "公司新闻",
            "主要上涨与下跌个股",
        )
    ]
    assert all(heading in markdown for heading in headings)
    assert markdown.index("## 美股市场表现") < markdown.index("标普 500 日涨跌")
    assert markdown.index("## 经济数据与美联储动态") < markdown.index("CPI 同比")
    assert markdown.index("## 公司新闻") < markdown.index("公司公告披露")


def test_markdown_unclassified_claim_keeps_evidence_ids(tmp_path):
    source, manifest = _source(tmp_path, _payload())
    import_report(source, tmp_path / "site", manifest)
    markdown = (tmp_path / "site/reports/2026-09-19-market-daily.md").read_text()
    assert "## 其他已核实内容" in markdown
    assert "证据：`index.spx.change_percent`" in markdown


def test_import_requires_matching_public_manifest_and_omits_private_fields(tmp_path):
    payload = _payload()
    payload["private_research_draft"] = "never publish this"
    payload["facts"][0]["private_passage"] = "not public"
    payload["events"] = [
        {
            "id": "reviewed.event.1",
            "title": "unreviewed private draft title",
            "actual": "unreviewed private draft actual",
            "source_url": "https://example.test/report",
        }
    ]
    payload["claims"][0]["evidence_ids"].append("reviewed.event.1")
    source, manifest = _source(tmp_path, payload)
    output = tmp_path / "site"
    assert import_report(source, output, manifest) == "2026-09-19"
    public = (output / "data/market_daily_report.json").read_text()
    assert json.loads(public)["report_formats"] == ["md", "txt"]
    assert "private_research_draft" not in public
    assert "private_passage" not in public
    assert "unreviewed private draft title" not in public
    assert "unreviewed private draft actual" not in public
    assert json.loads(public)["events"] == [{"id": "reviewed.event.1"}]
    bad = json.loads(manifest.read_text())
    bad["publication"] = "private"
    manifest.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="public manifest"):
        import_report(source, output, manifest)


def test_import_rejects_rehashed_file_with_invalid_content_hash(tmp_path):
    source, manifest = _source(tmp_path, _payload())
    payload = json.loads(source.read_text())
    payload["claims"][0]["claim"] = "changed without content hash"
    source.write_text(json.dumps(payload))
    publication = json.loads(manifest.read_text())
    publication["report_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(publication))
    with pytest.raises(ValueError, match="content hash"):
        import_report(source, tmp_path / "site", manifest)


def test_import_accepts_private_snapshot_filename_bound_by_public_manifest(tmp_path):
    source, manifest = _source(tmp_path, _payload())
    snapshot = tmp_path / "input.json"
    snapshot.write_bytes(source.read_bytes())
    assert import_report(snapshot, tmp_path / "site", manifest) == "2026-09-19"


def test_import_rejects_duplicate_evidence_ids(tmp_path):
    payload = _payload()
    payload["facts"].append(dict(payload["facts"][0]))
    source, manifest = _source(tmp_path, payload)
    with pytest.raises(ValueError, match="duplicate"):
        import_report(source, tmp_path / "site", manifest)
