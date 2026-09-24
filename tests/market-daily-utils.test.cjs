const test = require("node:test");
const assert = require("node:assert/strict");
const { summarizeMarketDaily, formatMarketDailyStatus, buildMarketDailyCharts } = require("../market-daily-utils.js");

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
  assert.deepEqual(summary.gaps, ["美债收益率当日变动", "指数行情"]);
  assert.equal(summary.hasTextReport, false);
});

test("market daily status calls a report date a report date, including missing sources", () => {
  assert.equal(
    formatMarketDailyStatus({ date: "2026-09-23", gaps: ["指数行情"] }),
    "2026-09-23 美东报告日 · 逐项显示原始观测日。 尚缺：指数行情。",
  );
});

test("market daily hides fixture and invalid source data", () => {
  assert.equal(summarizeMarketDaily({ schema_version: "1.0", quality_summary: { status: "fixture" }, facts: [] }), null);
  assert.equal(summarizeMarketDaily({ schema_version: "1.0", run_id: "daily-2026-09-23", facts: [{ id: "macro.cpi_yoy", value: "3.4", source_url: "javascript:alert(1)" }] }), null);
});

test("market daily shows reviewed index returns, Treasury rates and cited explanations", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-23",
    as_of: "2026-09-24T08:30:00+00:00", quality_summary: { status: "ok" },
    report_formats: ["md", "txt"],
    missing_sources: [],
    facts: [
      { id: "index.spx.change_percent", value: -0.8, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://abcnews.com/amp/Business/example" },
      { id: "treasury.10y.change_bp", value: 15, quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
    ],
    events: [{ id: "reviewed.1", source_url: "https://abcnews.com/amp/Business/example" }],
    claims: [{ claim: "美联社认为美债收益率上升带来压力。", evidence_ids: ["reviewed.1"], sources: ["https://abcnews.com/amp/Business/example"] }],
  });
  assert.equal(summary.rows[0].text, "标普 500 日涨跌 -0.80%");
  assert.equal(summary.rows[0].sourceLabel, "报道来源");
  assert.equal(summary.rows[1].text, "10 年期美债收益率日变动 15.00 bp");
  assert.equal(summary.rows[1].sourceLabel, "美国财政部原始数据");
  assert.equal(summary.claims[0].text, "美联社认为美债收益率上升带来压力。");
  assert.deepEqual(summary.gaps, []);
  assert.equal(summary.hasTextReport, true);
  assert.match(formatMarketDailyStatus(summary), /次日核实更新/);
});

test("market daily groups reviewed explanations and company news by evidence section", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-23", facts: [
      { id: "index.spx.change_percent", value: -0.8, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://example.test/close" },
    ],
    events: [{ id: "reviewed.1" }, { id: "reviewed.2" }],
    claims: [
      { claim: "收益率影响市场", evidence_ids: ["reviewed.1"], sources: ["https://example.test/close"] },
      { claim: "公司发布业绩", evidence_ids: ["reviewed.2"], sources: ["https://example.test/company"] },
    ],
    sections: [
      { key: "drivers", title: "市场驱动因素", claims: ["reviewed.1"] },
      { key: "company_news", title: "公司新闻", claims: ["reviewed.2"] },
    ],
  });
  assert.deepEqual(summary.claimSections.map((section) => [section.key, section.claims.map((claim) => claim.text)]), [
    ["drivers", ["收益率影响市场"]], ["company_news", ["公司发布业绩"]],
  ]);
});

test("market daily charts keep signed values and source dates in separate units", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-23", facts: [
      { id: "index.spx.change_percent", value: -0.8, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://abcnews.com/amp/Business/example" },
      { id: "index.dow.change_percent", value: 0.4, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://abcnews.com/amp/Business/example" },
      { id: "treasury.2y.change_bp", value: 14, quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
      { id: "treasury.10y.change_bp", value: 15, quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
    ],
  });
  const charts = buildMarketDailyCharts(summary);
  assert.deepEqual(charts.map((chart) => [chart.title, chart.unit, chart.rows.length]), [
    ["四大指数收盘涨跌", "%", 2], ["美债收益率当日变动", "bp", 2],
  ]);
  assert.deepEqual(charts[0].rows.map((row) => [row.valueText, row.side, row.width]), [
    ["-0.80%", "negative", 100], ["+0.40%", "positive", 50],
  ]);
  assert.deepEqual(charts[1].rows.map((row) => row.label), ["2 年期美债", "10 年期美债"]);
  assert.equal(charts[1].rows[0].valueText, "+14.00 bp");
  assert.equal(charts[1].rows[0].observationDate, "2026-09-23");
  assert.match(charts[1].rows[0].sourceUrl, /^https:\/\/home\.treasury\.gov\//);
});
