const test = require("node:test");
const assert = require("node:assert/strict");
const { summarizeMarketDaily } = require("../market-daily-utils.js");

test("market daily keeps the observation date and lagged yield state", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0",
    run_id: "daily-2026-09-23",
    quality_summary: { status: "degraded" },
    missing_sources: ["rates_lag", "quotes"],
    facts: [
      { id: "treasury.10y.change_bp", value: -5, quality: "lagged", observation_date: "2026-09-22", source_url: "https://fred.stlouisfed.org/series/DGS10" },
      { id: "macro.cpi_yoy", value: 3.4, quality: "ok", observation_date: "2026-08-01", source_url: "https://fred.stlouisfed.org/series/CPIAUCNS" },
    ],
  });

  assert.equal(summary.date, "2026-09-23");
  assert.equal(summary.rows[0].text, "10 年期美债收益率日变动 -5.00 bp");
  assert.equal(summary.rows[0].observationDate, "2026-09-22");
  assert.equal(summary.rows[0].quality, "lagged");
  assert.equal(summary.rows[1].text, "CPI 同比 3.40%");
  assert.deepEqual(summary.gaps, ["当日收益率", "指数行情"]);
});

test("market daily hides fixture and invalid source data", () => {
  assert.equal(summarizeMarketDaily({ schema_version: "1.0", quality_summary: { status: "fixture" }, facts: [] }), null);
  assert.equal(summarizeMarketDaily({ schema_version: "1.0", run_id: "daily-2026-09-23", facts: [{ id: "macro.cpi_yoy", value: "3.4", source_url: "javascript:alert(1)" }] }), null);
});
