"""Preview and apply are separate, and prior public revisions remain archived."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.import_charts import import_charts
from tests.test_chart_contract import public_chart, rehash


@pytest.fixture
def site_root(tmp_path: Path) -> Path:
    root = tmp_path / "site"
    (root / "data").mkdir(parents=True)
    (root / "data/reports.json").write_text(
        json.dumps(
            {
                "schema_version": "market_intel_pages.reports.v1",
                "reports": [{"id": "2026-09-18-morning", "date": "2026-09-18", "kind": "morning"}],
            }
        ),
        encoding="utf-8",
    )
    return root


@pytest.fixture
def public_chart_path(tmp_path: Path) -> Path:
    path = tmp_path / "input.json"
    path.write_text(json.dumps(public_chart()), encoding="utf-8")
    return path


def test_preview_does_not_write(site_root: Path, public_chart_path: Path, tmp_path: Path):
    archive = tmp_path / "archive"
    result = import_charts(site_root, public_chart_path, archive)
    assert result == {"changed": 1, "report_id": "2026-09-18-morning", "applied": False}
    assert not (site_root / "data/charts/2026-09-18-morning.json").exists()
    assert not archive.exists()


def test_apply_archives_prior_version_and_is_idempotent(
    site_root: Path, public_chart_path: Path, tmp_path: Path
):
    archive = tmp_path / "archive"
    first = import_charts(site_root, public_chart_path, archive, apply=True)
    assert first["applied"] is True
    destination = site_root / "data/charts/2026-09-18-morning.json"
    old = destination.read_bytes()
    assert import_charts(site_root, public_chart_path, archive, apply=True)["changed"] == 0
    revised = public_chart()
    revised["charts"][0]["points"][0]["value"] = 110.0
    public_chart_path.write_text(json.dumps(rehash(revised)), encoding="utf-8")
    assert import_charts(site_root, public_chart_path, archive, apply=True)["changed"] == 1
    assert destination.read_bytes() != old
    assert any(path.read_bytes() == old for path in archive.rglob("*.json"))


def test_candidate_and_wrong_report_are_rejected(site_root: Path, public_chart_path: Path, tmp_path: Path):
    candidate = public_chart()
    candidate["publication"] = "candidate"
    public_chart_path.write_text(json.dumps(rehash(candidate)), encoding="utf-8")
    with pytest.raises(ValueError, match="public"):
        import_charts(site_root, public_chart_path, tmp_path / "archive", apply=True)
    assert not (site_root / "data/charts").exists()
