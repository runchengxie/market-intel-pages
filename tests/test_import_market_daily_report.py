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
