const MARKET_DAILY_FACTS = [
  ["index.spx.change_percent", "标普 500 日涨跌", "%"],
  ["index.dow.change_percent", "道指日涨跌", "%"],
  ["index.nasdaq.change_percent", "纳指日涨跌", "%"],
  ["index.russell2000.change_percent", "罗素 2000 日涨跌", "%"],
  ["treasury.2y.change_bp", "2 年期美债收益率日变动", " bp"],
  ["treasury.5y.change_bp", "5 年期美债收益率日变动", " bp"],
  ["treasury.10y.change_bp", "10 年期美债收益率日变动", " bp"],
  ["treasury.30y.change_bp", "30 年期美债收益率日变动", " bp"],
  ["macro.cpi_yoy", "CPI 同比", "%"],
  ["macro.pce_yoy", "PCE 同比", "%"],
  ["macro.unemployment_rate", "失业率", "%"],
  ["macro.payroll_change_thousands", "非农就业月变动", " 千人"],
];
const FRED_SOURCE = /^https:\/\/fred\.stlouisfed\.org\/series\/[A-Z0-9]+$/;
const TREASURY_SOURCE = /^https:\/\/home\.treasury\.gov\/resource-center\/data-chart-center\/interest-rates\/daily-treasury-rates\.csv\/all\/\d{6}\?_format=csv&field_tdr_date_value_month=\d{6}&page=&type=daily_treasury_yield_curve$/;
const MARKET_DAILY_GAPS = {
  rates_lag: "美债收益率当日变动", quotes: "指数行情", research: "研究解释", fred: "部分 FRED 数据",
};

function summarizeMarketDaily(payload) {
  if (!payload || !/^1\./.test(payload.schema_version ?? "")
      || payload.quality_summary?.status === "fixture"
      || !/^daily-\d{4}-\d{2}-\d{2}$/.test(payload.run_id ?? "")
      || !Array.isArray(payload.facts)) return null;
  const rows = [];
  for (const [id, label, unit] of MARKET_DAILY_FACTS) {
    const fact = payload.facts.find((item) => item.id === id);
    if (!fact) continue;
    const sourceUrl = fact.source_url ?? "";
    const isIndex = id.startsWith("index.");
    const isTreasury = id.startsWith("treasury.") && TREASURY_SOURCE.test(sourceUrl);
    const validSource = isIndex
      ? fact.quality === "reviewed" && /^https:\/\/[^\s/]+\//.test(sourceUrl)
      : isTreasury || FRED_SOURCE.test(sourceUrl);
    if (typeof fact.value !== "number" || !Number.isFinite(fact.value)
        || !/^\d{4}-\d{2}-\d{2}$/.test(fact.observation_date ?? "")
        || !validSource) return null;
    rows.push({
      id,
      label: label.replace(/日涨跌|收益率日变动/g, "").trim(),
      value: fact.value,
      text: `${label} ${fact.value.toFixed(2)}${unit}`,
      observationDate: fact.observation_date,
      sourceUrl,
      sourceLabel: isIndex ? "报道来源" : isTreasury ? "美国财政部原始数据" : "FRED 原始数据",
      quality: fact.quality,
    });
  }
  if (!rows.length) return null;
  const evidenceIds = new Set([...(payload.facts ?? []), ...(payload.events ?? [])].map((item) => item.id));
  const claims = [];
  for (const claim of payload.claims ?? []) {
    if (typeof claim.claim !== "string" || !claim.claim.trim()
        || !Array.isArray(claim.evidence_ids) || !claim.evidence_ids.length
        || !claim.evidence_ids.every((id) => evidenceIds.has(id))
        || !Array.isArray(claim.sources) || !claim.sources.length
        || !claim.sources.every((url) => /^https:\/\/[^\s/]+\//.test(url))) return null;
    claims.push({ text: claim.claim, sourceUrls: claim.sources });
  }
  const gaps = (payload.missing_sources ?? [])
    .filter((item) => Object.hasOwn(MARKET_DAILY_GAPS, item))
    .map((item) => MARKET_DAILY_GAPS[item]);
  const date = payload.run_id.slice(6);
  const parts = payload.as_of
    ? new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(payload.as_of))
    : [];
  const updatedDate = parts.length
    ? ["year", "month", "day"].map((type) => parts.find((part) => part.type === type).value).join("-")
    : date;
  return { date, rows, claims, gaps, nextMorningRevision: updatedDate !== date };
}

function buildMarketDailyCharts(summary) {
  if (!summary) return [];
  const definitions = [
    { title: "四大指数收盘涨跌", unit: "%", prefix: "index." },
    { title: "美债收益率当日变动", unit: "bp", prefix: "treasury." },
  ];
  return definitions.map(({ title, unit, prefix }) => {
    const rows = summary.rows.filter((row) => row.id.startsWith(prefix)
      && row.observationDate === summary.date && row.quality !== "lagged");
    const maximum = Math.max(...rows.map((row) => Math.abs(row.value)), 0);
    return {
      title, unit,
      rows: rows.map((row) => ({
        ...row,
        side: row.value < 0 ? "negative" : "positive",
        width: maximum ? Math.abs(row.value) / maximum * 100 : 0,
        valueText: `${row.value >= 0 ? "+" : ""}${row.value.toFixed(2)}${unit === "%" ? "%" : " bp"}`,
      })),
    };
  }).filter((chart) => chart.rows.length);
}

function formatMarketDailyStatus(summary) {
  return `${summary.date} 美东报告日 · 逐项显示原始观测日。`
    + (summary.nextMorningRevision ? " 次日核实更新。" : "")
    + (summary.gaps.length ? ` 尚缺：${summary.gaps.join("、")}。` : "");
}

if (typeof module !== "undefined") module.exports = { summarizeMarketDaily, formatMarketDailyStatus, buildMarketDailyCharts };
if (typeof window !== "undefined") window.marketDailyUtils = { summarizeMarketDaily, formatMarketDailyStatus, buildMarketDailyCharts };
