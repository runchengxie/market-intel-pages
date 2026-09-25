const test = require("node:test");
const assert = require("node:assert/strict");
const { summarizeMarketDaily, formatMarketDailyStatus, buildMarketDailyCharts, buildMarketDailyChartSvg } = require("../market-daily-utils.js");

test("market daily keeps the observation date and lagged yield state", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0",
    run_id: "daily-2026-09-23",
    quality_summary: { status: "degraded" },
    missing_sources: ["rates_lag", "quotes"],
    facts: [
      { id: "treasury.10y.change_bp", metric: "yield_change", value: -5, unit: "basis_points", quality: "lagged", observation_date: "2026-09-22", source_url: "https://fred.stlouisfed.org/series/DGS10" },
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
  assert.equal(summarizeMarketDaily({ schema_version: "1.0", run_id: "daily-2026-09-23", facts: [{ id: "index.spx.change_percent", value: 1, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://[bad]/close" }] }), null);
});

test("market daily shows reviewed index returns, Treasury rates and cited explanations", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-23",
    as_of: "2026-09-24T08:30:00+00:00", quality_summary: { status: "ok" },
    report_formats: ["md", "txt"],
    missing_sources: [],
    facts: [
      { id: "index.spx.change_percent", value: -0.8, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://abcnews.com/amp/Business/example" },
      { id: "treasury.10y.change_bp", metric: "yield_change", value: 15, unit: "basis_points", quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
    ],
    events: [{ id: "reviewed.1", source_url: "https://abcnews.com/amp/Business/example" }],
    claims: [{ claim: "美联社认为美债收益率上升带来压力。", evidence_ids: ["reviewed.1"], sources: ["https://abcnews.com/amp/Business/example"] }],
  });
  assert.equal(summary.rows[0].text, "标普 500 日涨跌 -0.80%");
  assert.equal(summary.rows[0].sourceLabel, "核实报道");
  assert.equal(summary.rows[1].text, "10 年期美债收益率日变动 15.00 bp");
  assert.equal(summary.rows[1].sourceLabel, "美国财政部");
  assert.equal(summary.claims[0].text, "美联社认为美债收益率上升带来压力。");
  assert.deepEqual(summary.gaps, []);
  assert.equal(summary.hasTextReport, true);
  assert.match(formatMarketDailyStatus(summary), /次日核实更新/);
});

test("market daily accepts same-day Treasury levels and cross-asset futures facts only", () => {
  const treasuryUrl = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve";
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-24", as_of: "2026-09-25T11:00:00Z",
    quality_summary: { status: "ok" }, missing_sources: [], facts: [
      { id: "treasury.2y.level_percent", metric: "yield_level", value: 4.1, unit: "percent", quality: "ok", observation_date: "2026-09-24", source_url: treasuryUrl },
      { id: "treasury.2y.change_bp", metric: "yield_change", value: 5, unit: "basis_points", quality: "ok", observation_date: "2026-09-24", source_url: treasuryUrl },
      { id: "treasury.10y.level_percent", metric: "yield_level", value: 4.2, unit: "percent", quality: "ok", observation_date: "2026-09-24", source_url: treasuryUrl },
      { id: "treasury.10y.change_bp", metric: "yield_change", value: 7, unit: "basis_points", quality: "ok", observation_date: "2026-09-24", source_url: treasuryUrl },
      ...[["brent", "BZ%3DF", "USD/barrel", 71], ["gold", "GC%3DF", "USD/troy_ounce", 3900], ["silver", "SI%3DF", "USD/troy_ounce", 47], ["bitcoin", "BTC%3DF", "USD/bitcoin", 108000]].flatMap(([name, ticker, unit, price]) => [
        { id: `cross_asset.${name}.close`, metric: name === "bitcoin" ? "crypto_futures_close" : "commodity_close", value: price, unit, quality: "ok", observation_date: "2026-09-24", source_url: `https://finance.yahoo.com/quote/${ticker}/history/` },
        { id: `cross_asset.${name}.change_percent`, metric: "daily_return", value: 1.2, unit: "percent", quality: "ok", observation_date: "2026-09-24", source_url: `https://finance.yahoo.com/quote/${ticker}/history/` },
      ]),
    ],
  });

  assert.ok(summary);
  assert.equal(summary.rateRows.length, 2);
  assert.equal(summary.rateRows[1].levelValue, 4.2);
  assert.equal(summary.crossAssetRows.length, 4);
  assert.deepEqual(summary.crossAssetRows.map((row) => row.name), ["brent", "gold", "silver", "bitcoin"]);
  assert.equal(summary.crossAssetRows[3].priceValue, 108000);
  assert.equal(summary.rows.some((row) => row.id === "cross_asset.brent.close"), true);
  const svg = buildMarketDailyChartSvg(summary);
  assert.match(svg, /美债收益率水平与日变动/);
  assert.match(svg, /4\.20%/);
  assert.match(svg, /布伦特期货收盘：71 USD\/barrel/);
  assert.match(svg, /CME 比特币期货收盘：108,000 USD\/bitcoin/);
});

test("market daily rejects cross-asset facts with mismatched dates, units or sources", () => {
  for (const override of [
    { observation_date: "2026-09-23" },
    { unit: "USD/contract" },
    { source_url: "https://example.test/price" },
  ]) {
    const summary = summarizeMarketDaily({
      schema_version: "1.0", run_id: "daily-2026-09-24", facts: [
        { id: "cross_asset.bitcoin.close", metric: "crypto_futures_close", value: 108000, unit: "USD/bitcoin", quality: "ok", observation_date: "2026-09-24", source_url: "https://finance.yahoo.com/quote/BTC%3DF/history/", ...override },
      ],
    });
    assert.equal(summary, null);
  }
});

test("market daily caps visible driver and mover claims at three each", () => {
  const drivers = [1, 2, 3, 4].map((number) => `driver.${number}`);
  const movers = [1, 2, 3, 4].map((number) => `mover.${number}`);
  const ids = [...drivers, ...movers];
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-24",
    facts: [
      { id: "index.spx.change_percent", value: 0.2, unit: "percent", quality: "reviewed", observation_date: "2026-09-24", source_url: "https://example.com/close" },
      ...ids.map((id) => ({ id })),
    ],
    claims: ids.map((id) => ({ claim: id, evidence_ids: [id], sources: ["https://example.com/evidence"] })),
    sections: [
      { key: "drivers", claims: drivers },
      { key: "movers", claims: movers },
      { key: "company_news", claims: ["company.1"] },
    ],
  });

  assert.deepEqual(summary.primaryClaims.map((section) => [section.key, section.claims.length]), [
    ["drivers", 3], ["movers", 3],
  ]);
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
      { id: "treasury.2y.change_bp", metric: "yield_change", value: 14, unit: "basis_points", quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
      { id: "treasury.10y.change_bp", metric: "yield_change", value: 15, unit: "basis_points", quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
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

test("chart image uses reviewed report-date facts with dates, units and source hosts", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-23", facts: [
      { id: "index.spx.change_percent", value: -0.8, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://abcnews.com/Business/close" },
      { id: "index.dow.change_percent", value: 0.4, quality: "reviewed", observation_date: "2026-09-23", source_url: "https://abcnews.com/Business/close" },
      { id: "treasury.10y.change_bp", metric: "yield_change", value: 15, unit: "basis_points", quality: "ok", observation_date: "2026-09-23", source_url: "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/all/202609?_format=csv&field_tdr_date_value_month=202609&page=&type=daily_treasury_yield_curve" },
      { id: "treasury.2y.change_bp", metric: "yield_change", value: 14, unit: "basis_points", quality: "lagged", observation_date: "2026-09-22", source_url: "https://fred.stlouisfed.org/series/DGS2" },
    ],
  });
  const svg = buildMarketDailyChartSvg?.(summary) ?? "";
  assert.match(svg, /<svg[^>]*width="960"/);
  assert.match(svg, /2026-09-23 美东交易日/);
  assert.match(svg, /标普 500/);
  assert.match(svg, /-0\.80%/);
  assert.match(svg, /\+0\.40%/);
  assert.match(svg, /\+15\.00 bp/);
  assert.match(svg, /观测日 2026-09-23/);
  assert.match(svg, /abcnews\.com/);
  assert.match(svg, /home\.treasury\.gov/);
  assert.doesNotMatch(svg, /2026-09-22|FRED 原始数据|<script>/);
});

test("chart image has no invented marks when no report-date chart facts exist", () => {
  const summary = summarizeMarketDaily({
    schema_version: "1.0", run_id: "daily-2026-09-23", facts: [
      { id: "treasury.10y.change_bp", metric: "yield_change", value: 15, unit: "basis_points", quality: "lagged", observation_date: "2026-09-22", source_url: "https://fred.stlouisfed.org/series/DGS10" },
    ],
  });
  assert.equal(buildMarketDailyChartSvg?.(summary) ?? null, null);
});
