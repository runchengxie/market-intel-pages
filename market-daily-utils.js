const MARKET_DAILY_FACTS = [
  ["treasury.10y.change_bp", "10 年期美债收益率日变动", " bp"],
  ["treasury.2y.change_bp", "2 年期美债收益率日变动", " bp"],
  ["treasury.5y.change_bp", "5 年期美债收益率日变动", " bp"],
  ["treasury.30y.change_bp", "30 年期美债收益率日变动", " bp"],
  ["macro.cpi_yoy", "CPI 同比", "%"],
  ["macro.pce_yoy", "PCE 同比", "%"],
  ["macro.unemployment_rate", "失业率", "%"],
  ["macro.payroll_change_thousands", "非农就业月变动", " 千人"],
];
const MARKET_DAILY_GAPS = {
  rates_lag: "当日收益率", quotes: "指数行情", research: "研究解释", fred: "部分 FRED 数据",
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
    if (typeof fact.value !== "number" || !Number.isFinite(fact.value)
        || !/^\d{4}-\d{2}-\d{2}$/.test(fact.observation_date ?? "")
        || !/^https:\/\/fred\.stlouisfed\.org\/series\/[A-Z0-9]+$/.test(fact.source_url ?? "")) return null;
    rows.push({
      text: `${label} ${fact.value.toFixed(2)}${unit}`,
      observationDate: fact.observation_date,
      sourceUrl: fact.source_url,
      quality: fact.quality,
    });
  }
  if (!rows.length) return null;
  const gaps = (payload.missing_sources ?? [])
    .filter((item) => Object.hasOwn(MARKET_DAILY_GAPS, item))
    .map((item) => MARKET_DAILY_GAPS[item]);
  return { date: payload.run_id.slice(6), rows, gaps };
}

if (typeof module !== "undefined") module.exports = { summarizeMarketDaily };
if (typeof window !== "undefined") window.marketDailyUtils = { summarizeMarketDaily };
