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
const MARKET_DAILY_CLAIM_SECTIONS = [
  ["market", "市场表现"], ["drivers", "市场驱动因素"],
  ["macro", "经济数据与美联储动态"], ["company_news", "公司新闻"],
  ["movers", "主要上涨与下跌个股"], ["other", "其他已核实内容"],
];

function validHttpSource(sourceUrl) {
  try {
    const parsed = new URL(sourceUrl);
    return parsed.protocol === "https:" && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

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
      ? fact.quality === "reviewed" && validHttpSource(sourceUrl)
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
  const sectionByEvidence = new Map();
  for (const [key] of MARKET_DAILY_CLAIM_SECTIONS) {
    const section = (payload.sections ?? []).find((item) => item.key === key);
    for (const id of Array.isArray(section?.claims) ? section.claims : []) {
      if (typeof id === "string" && !sectionByEvidence.has(id)) sectionByEvidence.set(id, key);
    }
  }
  const claims = [];
  for (const claim of payload.claims ?? []) {
    if (typeof claim.claim !== "string" || !claim.claim.trim()
        || !Array.isArray(claim.evidence_ids) || !claim.evidence_ids.length
        || !claim.evidence_ids.every((id) => evidenceIds.has(id))
        || !Array.isArray(claim.sources) || !claim.sources.length
        || !claim.sources.every(validHttpSource)) return null;
    const sectionKey = claim.evidence_ids.map((id) => sectionByEvidence.get(id)).find(Boolean) ?? "other";
    claims.push({ text: claim.claim, sourceUrls: claim.sources, sectionKey });
  }
  const claimSections = MARKET_DAILY_CLAIM_SECTIONS.map(([key, title]) => ({
    key, title, claims: claims.filter((claim) => claim.sectionKey === key),
  })).filter((section) => section.claims.length);
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
  const hasTextReport = Array.isArray(payload.report_formats)
    && payload.report_formats.includes("txt") && payload.report_formats.includes("md");
  return { date, rows, claims, claimSections, gaps, hasTextReport, nextMorningRevision: updatedDate !== date };
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

function escapeSvgText(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;",
  })[character]);
}

function buildMarketDailyChartSvg(summary) {
  const charts = buildMarketDailyCharts(summary);
  if (!charts.length) return null;
  const height = 134 + charts.reduce((total, chart) => total + 54 + chart.rows.length * 58, 0) + 50;
  let y = 118;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="${height}" viewBox="0 0 960 ${height}" role="img">`,
    `<title>${escapeSvgText(summary.date)} 美东交易日市场图表</title>`,
    `<desc>仅展示报告日已核实的指数收盘涨跌及美债收益率当日变动。每项均标明观测日和来源域名。</desc>`,
    `<rect width="960" height="${height}" fill="#fff9f2"/>`,
    `<text x="54" y="62" fill="#34271f" font-family="sans-serif" font-size="28" font-weight="700">${escapeSvgText(summary.date)} 美东交易日</text>`,
    `<text x="54" y="91" fill="#715f52" font-family="sans-serif" font-size="15">美股市场速览 · 仅含已核实的同日数值</text>`,
  ];
  for (const chart of charts) {
    parts.push(`<text x="54" y="${y}" fill="#34271f" font-family="sans-serif" font-size="19" font-weight="700">${escapeSvgText(chart.title)}（${escapeSvgText(chart.unit)}）</text>`);
    y += 34;
    for (const row of chart.rows) {
      const center = 565;
      const width = Math.round(row.width * 2.15);
      const barX = row.side === "negative" ? center - width : center;
      const color = row.side === "negative" ? "#9e806d" : "#c74f36";
      const host = new URL(row.sourceUrl).hostname;
      parts.push(`<text x="54" y="${y + 5}" fill="#34271f" font-family="sans-serif" font-size="16" font-weight="600">${escapeSvgText(row.label)}</text>`);
      parts.push(`<rect x="350" y="${y - 13}" width="430" height="18" rx="3" fill="#f2e7dc"/>`);
      parts.push(`<rect x="${barX}" y="${y - 11}" width="${width}" height="14" rx="2" fill="${color}"/>`);
      parts.push(`<line x1="${center}" y1="${y - 16}" x2="${center}" y2="${y + 8}" stroke="#5d4c40" stroke-width="1"/>`);
      parts.push(`<text x="800" y="${y + 5}" fill="#34271f" font-family="monospace" font-size="16" font-weight="700">${escapeSvgText(row.valueText)}</text>`);
      parts.push(`<text x="54" y="${y + 25}" fill="#715f52" font-family="sans-serif" font-size="12">观测日 ${escapeSvgText(row.observationDate)} · 来源 ${escapeSvgText(host)}</text>`);
      y += 58;
    }
    y += 20;
  }
  parts.push(`<line x1="54" y1="${height - 48}" x2="906" y2="${height - 48}" stroke="#d9c7b6"/>`);
  parts.push(`<text x="54" y="${height - 22}" fill="#715f52" font-family="sans-serif" font-size="12">来源详情和核实说明请见同日报告；市场有风险，投资需谨慎。</text>`);
  parts.push("</svg>");
  return parts.join("");
}

function formatMarketDailyStatus(summary) {
  return `${summary.date} 美东报告日 · 逐项显示原始观测日。`
    + (summary.nextMorningRevision ? " 次日核实更新。" : "")
    + (summary.gaps.length ? ` 尚缺：${summary.gaps.join("、")}。` : "");
}

if (typeof module !== "undefined") module.exports = { summarizeMarketDaily, formatMarketDailyStatus, buildMarketDailyCharts, buildMarketDailyChartSvg };
if (typeof window !== "undefined") window.marketDailyUtils = { summarizeMarketDaily, formatMarketDailyStatus, buildMarketDailyCharts, buildMarketDailyChartSvg };
