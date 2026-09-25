const MARKET_DAILY_FACTS = [
  ["index.spx.change_percent", "标普 500 日涨跌", "%"],
  ["index.dow.change_percent", "道指日涨跌", "%"],
  ["index.nasdaq.change_percent", "纳指日涨跌", "%"],
  ["index.russell2000.change_percent", "罗素 2000 日涨跌", "%"],
  ["treasury.2y.change_bp", "2 年期美债收益率日变动", " bp"],
  ["treasury.5y.change_bp", "5 年期美债收益率日变动", " bp"],
  ["treasury.10y.change_bp", "10 年期美债收益率日变动", " bp"],
  ["treasury.30y.change_bp", "30 年期美债收益率日变动", " bp"],
  ["treasury.2y.level_percent", "2 年期美债收益率水平", "%"],
  ["treasury.5y.level_percent", "5 年期美债收益率水平", "%"],
  ["treasury.10y.level_percent", "10 年期美债收益率水平", "%"],
  ["treasury.30y.level_percent", "30 年期美债收益率水平", "%"],
  ["cross_asset.brent.close", "布伦特期货收盘", " 美元/桶"],
  ["cross_asset.brent.change_percent", "布伦特日涨跌", "%"],
  ["cross_asset.gold.close", "COMEX 黄金期货收盘", " 美元/金衡盎司"],
  ["cross_asset.gold.change_percent", "黄金日涨跌", "%"],
  ["cross_asset.silver.close", "COMEX 白银期货收盘", " 美元/金衡盎司"],
  ["cross_asset.silver.change_percent", "白银日涨跌", "%"],
  ["cross_asset.bitcoin.close", "CME 比特币期货收盘", " 美元/BTC"],
  ["cross_asset.bitcoin.change_percent", "比特币期货日涨跌", "%"],
  ["macro.cpi_yoy", "CPI 同比", "%"],
  ["macro.pce_yoy", "PCE 同比", "%"],
  ["macro.unemployment_rate", "失业率", "%"],
  ["macro.payroll_change_thousands", "非农就业月变动", " 千人"],
];
const FRED_SOURCE = /^https:\/\/fred\.stlouisfed\.org\/series\/[A-Z0-9]+$/;
const TREASURY_SOURCE = /^https:\/\/home\.treasury\.gov\/resource-center\/data-chart-center\/interest-rates\/daily-treasury-rates\.csv\/all\/\d{6}\?_format=csv&field_tdr_date_value_month=\d{6}&page=&type=daily_treasury_yield_curve$/;
const YAHOO_SOURCES = {
  brent: /^https:\/\/finance\.yahoo\.com\/quote\/BZ%3DF\/history\/$/,
  gold: /^https:\/\/finance\.yahoo\.com\/quote\/GC%3DF\/history\/$/,
  silver: /^https:\/\/finance\.yahoo\.com\/quote\/SI%3DF\/history\/$/,
  bitcoin: /^https:\/\/finance\.yahoo\.com\/quote\/BTC%3DF\/history\/$/,
};
const MARKET_DAILY_GAPS = {
  rates_lag: "美债收益率当日变动", quotes: "指数行情", research: "研究解释", fred: "部分 FRED 数据",
  cross_asset: "布伦特、金银或比特币行情",
};
const MARKET_DAILY_CLAIM_SECTIONS = [
  ["market", "市场表现"], ["drivers", "市场驱动因素"], ["movers", "主要个股"],
  ["macro", "经济数据与美联储动态"], ["company_news", "公司新闻"],
  ["other", "其他已核实内容"],
];

function validHttpSource(sourceUrl) {
  try {
    const parsed = new URL(sourceUrl);
    return parsed.protocol === "https:" && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

function validMarketDailyFact(id, fact, reportDate) {
  const url = fact.source_url ?? "";
  if (id.startsWith("index.")) {
    return fact.quality === "reviewed" && validHttpSource(url)
      && fact.observation_date === reportDate;
  }
  if (id.startsWith("treasury.")) {
    const isLevel = id.endsWith(".level_percent");
    const expectedUnit = isLevel ? "percent" : "basis_points";
    const expectedMetric = isLevel ? "yield_level" : "yield_change";
    return fact.unit === expectedUnit
      && fact.metric === expectedMetric
      && ((TREASURY_SOURCE.test(url) && fact.quality === "ok") || FRED_SOURCE.test(url));
  }
  if (id.startsWith("cross_asset.")) {
    const [, asset, field] = id.split(".");
    const source = YAHOO_SOURCES[asset];
    const isClose = field === "close";
    const units = { brent: "USD/barrel", gold: "USD/troy_ounce", silver: "USD/troy_ounce", bitcoin: "USD/bitcoin" };
    const metric = isClose ? (asset === "bitcoin" ? "crypto_futures_close" : "commodity_close") : "daily_return";
    return Boolean(source) && source.test(url) && fact.quality === "ok"
      && fact.observation_date === reportDate
      && fact.unit === (isClose ? units[asset] : "percent")
      && fact.metric === metric;
  }
  if (id.startsWith("macro.")) return FRED_SOURCE.test(url);
  return false;
}

function summarizeMarketDaily(payload) {
  if (!payload || !/^1\./.test(payload.schema_version ?? "")
      || payload.quality_summary?.status === "fixture"
      || !/^daily-\d{4}-\d{2}-\d{2}$/.test(payload.run_id ?? "")
      || !Array.isArray(payload.facts)) return null;
  const date = payload.run_id.slice(6);
  const rows = [];
  for (const [id, label, unit] of MARKET_DAILY_FACTS) {
    const fact = payload.facts.find((item) => item.id === id);
    if (!fact) continue;
    const isIndex = id.startsWith("index.");
    const isTreasury = id.startsWith("treasury.");
    const isCrossAsset = id.startsWith("cross_asset.");
    if (typeof fact.value !== "number" || !Number.isFinite(fact.value)
        || !/^\d{4}-\d{2}-\d{2}$/.test(fact.observation_date ?? "")
        || !validMarketDailyFact(id, fact, date)) return null;
    const sourceUrl = fact.source_url;
    rows.push({
      id,
      label: label.replace(/日涨跌|收益率日变动/g, "").trim(),
      value: fact.value,
      text: `${label} ${fact.value.toFixed(2)}${unit}`,
      observationDate: fact.observation_date,
      sourceUrl,
      sourceLabel: isIndex ? "核实报道" : isTreasury && TREASURY_SOURCE.test(sourceUrl)
        ? "美国财政部" : isCrossAsset ? "Yahoo Finance" : "FRED",
      metric: fact.metric ?? "",
      unit: fact.unit ?? "",
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
  for (const tenor of ["2y", "5y", "10y", "30y"]) {
    const level = rows.find((row) => row.id === `treasury.${tenor}.level_percent`);
    const change = rows.find((row) => row.id === `treasury.${tenor}.change_bp`);
    if (level && change && (level.observationDate !== change.observationDate
        || level.sourceUrl !== change.sourceUrl || level.sourceLabel !== change.sourceLabel)) return null;
  }
  for (const asset of Object.keys(YAHOO_SOURCES)) {
    const close = rows.some((row) => row.id === `cross_asset.${asset}.close`);
    const change = rows.some((row) => row.id === `cross_asset.${asset}.change_percent`);
    if (close !== change) return null;
  }
  const rateRows = ["2y", "5y", "10y", "30y"].map((tenor) => {
    const level = rows.find((row) => row.id === `treasury.${tenor}.level_percent`);
    const change = rows.find((row) => row.id === `treasury.${tenor}.change_bp`);
    return level || change ? {
      tenor, label: `${tenor.slice(0, -1)} 年期美债`,
      levelValue: level?.value ?? null, changeValue: change?.value ?? null,
      observationDate: level?.observationDate ?? change?.observationDate,
      sourceUrl: level?.sourceUrl ?? change?.sourceUrl,
      sourceLabel: level?.sourceLabel ?? change?.sourceLabel,
    } : null;
  }).filter(Boolean);
  const crossAssetRows = ["brent", "gold", "silver", "bitcoin"].map((name) => {
    const close = rows.find((row) => row.id === `cross_asset.${name}.close`);
    const change = rows.find((row) => row.id === `cross_asset.${name}.change_percent`);
    return close && change ? { name, label: close.label, priceValue: close.value,
      priceUnit: close.unit, changeValue: change.value, observationDate: close.observationDate,
      sourceUrl: close.sourceUrl, sourceLabel: close.sourceLabel } : null;
  }).filter(Boolean);
  const parts = payload.as_of
    ? new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(new Date(payload.as_of))
    : [];
  const updatedDate = parts.length
    ? ["year", "month", "day"].map((type) => parts.find((part) => part.type === type).value).join("-")
    : date;
  const hasTextReport = Array.isArray(payload.report_formats)
    && payload.report_formats.includes("txt") && payload.report_formats.includes("md");
  const primaryClaims = claimSections
    .filter((section) => ["market", "drivers", "movers"].includes(section.key))
    .map((section) => ({ ...section, claims: section.claims.slice(0, 3) }));
  const secondaryClaimSections = claimSections
    .filter((section) => !["drivers", "movers"].includes(section.key));
  const secondaryRows = rows.filter((row) => row.id.startsWith("macro."));
  return { date, rows, rateRows, crossAssetRows, claims, claimSections, primaryClaims,
    secondaryClaimSections, secondaryRows, gaps, hasTextReport, nextMorningRevision: updatedDate !== date };
}

function buildMarketDailyCharts(summary) {
  if (!summary) return [];
  const definitions = [
    { title: "四大指数收盘涨跌", unit: "%", prefix: "index.", ids: [/^index\./] },
    { title: "美债收益率当日变动", unit: "bp", prefix: "treasury.", ids: [/\.change_bp$/] },
    { title: "跨资产日涨跌", unit: "%", prefix: "cross_asset.", ids: [/\.change_percent$/] },
  ];
  return definitions.map(({ title, unit, prefix, ids }) => {
    const rows = summary.rows.filter((row) => row.id.startsWith(prefix)
      && ids.some((pattern) => pattern.test(row.id))
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
  const freshRates = summary.rateRows.filter((row) => row.observationDate === summary.date);
  const supplementalHeight = (freshRates.length ? 54 + freshRates.length * 27 : 0)
    + (summary.crossAssetRows.length ? 54 + summary.crossAssetRows.length * 27 : 0);
  const height = 134 + charts.reduce((total, chart) => total + 54 + chart.rows.length * 58, 0)
    + supplementalHeight + 50;
  let y = 118;
  const parts = [
    `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="${height}" viewBox="0 0 960 ${height}" role="img">`,
    `<title>${escapeSvgText(summary.date)} 美东交易日市场图表</title>`,
    `<desc>展示报告日已核实的指数、收益率变动与跨资产行情，并列出美债水平、期货价格、观测日和来源。</desc>`,
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
  if (freshRates.length) {
    parts.push(`<text x="54" y="${y}" fill="#34271f" font-family="sans-serif" font-size="18" font-weight="700">美债收益率水平与日变动</text>`);
    y += 27;
    for (const row of freshRates) {
      const level = row.levelValue === null ? "—" : `${row.levelValue.toFixed(2)}%`;
      const change = row.changeValue === null ? "—" : `${row.changeValue >= 0 ? "+" : ""}${row.changeValue.toFixed(2)} bp`;
      parts.push(`<text x="54" y="${y}" fill="#34271f" font-family="sans-serif" font-size="14">${escapeSvgText(row.label)}：${escapeSvgText(level)} · ${escapeSvgText(change)} · ${escapeSvgText(row.observationDate)} · ${escapeSvgText(row.sourceLabel)}</text>`);
      y += 27;
    }
    y += 12;
  }
  if (summary.crossAssetRows.length) {
    parts.push(`<text x="54" y="${y}" fill="#34271f" font-family="sans-serif" font-size="18" font-weight="700">跨资产期货价格</text>`);
    y += 27;
    for (const row of summary.crossAssetRows) {
      const price = `${row.priceValue.toLocaleString("en-US", { maximumFractionDigits: 4 })} ${row.priceUnit}`;
      const change = `${row.changeValue >= 0 ? "+" : ""}${row.changeValue.toFixed(2)}%`;
      parts.push(`<text x="54" y="${y}" fill="#34271f" font-family="sans-serif" font-size="14">${escapeSvgText(row.label)}：${escapeSvgText(price)} · ${escapeSvgText(change)} · ${escapeSvgText(row.observationDate)} · Yahoo Finance</text>`);
      y += 27;
    }
    y += 12;
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
