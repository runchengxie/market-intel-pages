import json

import pytest

from scripts.import_market_daily_report import import_report


def _payload():
    return {
        "schema_version": "1.0",
        "as_of": "2026-09-19T01:00:00+00:00",
        "generated_at": "2026-09-19T01:00:00+00:00",
        "run_id": "daily-2026-09-19",
        "facts": [{"id": "index.spx.change_percent", "value": 0.16}],
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


def test_import_report_writes_public_json_and_markdown(tmp_path):
    source = tmp_path / "daily_report.json"
    source.write_text(json.dumps(_payload()), encoding="utf-8")
    output = tmp_path / "site"
    result = import_report(source, output)
    assert result == "2026-09-19"
    assert (output / "data/market_daily_report.json").exists()
    assert "SPX rose" in (output / "reports/2026-09-19-market-daily.md").read_text()


def test_import_report_rejects_credentials(tmp_path):
    payload = _payload()
    payload["claims"][0]["claim"] = "API_KEY leaked"
    source = tmp_path / "daily_report.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="credentials"):
        import_report(source, tmp_path / "site")


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
        missing_sources=["quotes", "research"],
    )
    source = tmp_path / "daily_report.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    assert import_report(source, tmp_path / "site") == "2026-09-23"
    markdown = (tmp_path / "site/reports/2026-09-23-market-daily.md").read_text()
    assert "10 年期美债收益率日变动：-5.00 bp" in markdown
    assert "CPI 同比：3.40%" in markdown
    assert "观测日 2026-08-01" in markdown
    assert "https://fred.stlouisfed.org/series/CPIAUCNS" in markdown
    assert "指数行情" in markdown


def test_import_report_rejects_fixture_status(tmp_path):
    payload = _payload()
    payload["quality_summary"]["status"] = "fixture"
    source = tmp_path / "daily_report.json"
    source.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="fixture"):
        import_report(source, tmp_path / "site")
