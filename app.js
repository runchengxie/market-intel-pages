const state = {
  reports: [],
  summaries: [],
  insights: [],
  outcomes: [],
  generation: {},
  kind: "all",
  date: "",
};

const reportList = document.querySelector("#report-list");
const emptyState = document.querySelector("#empty-state");
const loadError = document.querySelector("#load-error");
const summaryList = document.querySelector("#daily-summary-list");
const summaryEmpty = document.querySelector("#summary-empty");
const dateFilter = document.querySelector("#date-filter");

function renderMarketDaily(payload) {
  const summary = window.marketDailyUtils.summarizeMarketDaily(payload);
  const status = document.querySelector("#market-daily-status");
  const list = document.querySelector("#market-daily-list");
  if (!summary) {
    status.textContent = "美股宏观日报尚未发布，或数据未通过校验。";
    list.replaceChildren();
    return;
  }
  status.textContent = window.marketDailyUtils.formatMarketDailyStatus(summary);
  list.replaceChildren(...summary.rows.map((row) => {
    const card = makeElement("article", "market-daily-card");
    card.append(makeElement("p", "market-daily-value", row.text));
    const source = makeElement("a", "source-link", `观测日 ${row.observationDate} · FRED 原始数据`);
    source.href = row.sourceUrl;
    source.target = "_blank";
    source.rel = "noopener noreferrer";
    card.append(source);
    if (row.quality === "lagged") card.append(makeElement("span", "market-daily-lag", "当日数据未公布"));
    list.append(card);
    return card;
  }));
}

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function dateLabel(value) {
  const date = new Date(`${value}T12:00:00`);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  }).format(date);
}

function renderReport(report) {
  const article = makeElement("article", "report-card");
  article.id = report.id;
  const head = makeElement("div", "report-meta");
  const kind = report.kind === "morning" ? "晨报" : "晚报";
  head.append(
    makeElement("span", "report-type", kind),
    makeElement("time", "report-date", dateLabel(report.date)),
  );
  article.append(head, makeElement("h3", "report-title", report.title));
  article.append(makeElement("p", "report-summary", report.summary));
  if (report.generation_mode === "backfill") {
    article.append(makeElement("p", "replay-label", "补发报告：按该日行情重新整理，生成时间见原文。"));
  }

  const details = makeElement("details", "report-details");
  const summary = makeElement("summary", "details-toggle", "展开报告内容");
  const body = makeElement("div", "report-body");
  for (const section of report.sections ?? []) {
    const sectionElement = makeElement("section", "report-section");
    sectionElement.append(makeElement("h4", "", section.title));
    for (const paragraph of section.paragraphs ?? []) {
      sectionElement.append(makeElement("p", "", paragraph));
    }
    body.append(sectionElement);
  }
  if (/^reports\/[a-zA-Z0-9._-]+\.md$/.test(report.source_url ?? "")) {
    const source = makeElement("a", "source-link", "查看完整原文（Markdown）");
    source.href = report.source_url;
    source.setAttribute("download", "");
    body.append(source);
  }
  details.append(summary, body);
  article.append(details);
  return article;
}

function visibleReports() {
  return window.marketIntelUtils.selectVisibleReports(state.reports, state.date, state.kind);
}

function renderDailySummary(summary) {
  const article = makeElement("article", "daily-note-card");
  const date = makeElement("time", "daily-note-date", dateLabel(summary.date));
  date.dateTime = summary.date;
  article.append(date, makeElement("p", "daily-note-text", summary.text));
  return article;
}

function renderDailySummaries() {
  const summaries = window.marketIntelUtils.selectVisibleSummaries(
    state.summaries,
    state.reports,
    state.date,
  );
  summaryList.replaceChildren(...summaries.map(renderDailySummary));
  summaryEmpty.hidden = summaries.length !== 0;
}

function populateDateFilter() {
  const dates = [...new Set(state.reports.map((report) => report.date))]
    .sort((left, right) => right.localeCompare(left));
  dateFilter.replaceChildren(makeElement("option", "", "最近报告"));
  dateFilter.firstElementChild.value = "";
  for (const date of dates) {
    const option = makeElement("option", "", dateLabel(date));
    option.value = date;
    dateFilter.append(option);
  }
}

function render() {
  const reports = visibleReports();
  renderDailySummaries();
  renderInsights();
  reportList.replaceChildren(...reports.map(renderReport));
  emptyState.hidden = reports.length !== 0;
  document.querySelector("#section-title").textContent = state.date
    ? `${dateLabel(state.date)}的报告`
    : state.kind === "morning"
      ? "晨间报告"
      : state.kind === "evening"
        ? "晚间报告"
        : "最近交易日的报告";
  document.querySelector("#section-kicker").textContent = state.date
    ? "ARCHIVE"
    : state.kind === "all" ? "LATEST EDITION" : "DAILY EDITION";
}

function timestampLabel(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "时间未提供";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit",
  }).format(date);
}

function evidenceDetails(refs, evidence) {
  const details = makeElement("details", "evidence-details");
  details.append(makeElement("summary", "", "查看依据"));
  for (const ref of refs ?? []) {
    const item = evidence.find((entry) => entry.id === ref);
    if (!item) continue;
    const box = makeElement("div", "evidence-item");
    box.append(makeElement("span", "evidence-label", `${item.report_id} · ${item.section}`),
      makeElement("p", "", item.text));
    const report = state.reports.find((row) => row.id === item.report_id);
    if (report && /^reports\/[a-zA-Z0-9._-]+\.md$/.test(report.source_url ?? "")) {
      const source = makeElement("a", "source-link", "原报告");
      source.href = report.source_url;
      box.append(source);
    }
    details.append(box);
  }
  return details;
}

function renderInsight(note) {
  const card = makeElement("article", "insight-card");
  card.append(makeElement("div", "daily-note-date", dateLabel(note.date)),
    makeElement("p", "insight-overview", note.analysis.overview.text),
    evidenceDetails(note.analysis.overview.evidence_ids, note.evidence));
  const meta = `信息截至 ${timestampLabel(note.as_of)} · 解读生成 ${timestampLabel(note.generated_at)}（北京时间）`;
  card.append(makeElement("p", "insight-meta", meta));
  if (note.generation_mode === "retrospective") {
    card.append(makeElement("p", "replay-label", "历史材料回放：基于归档或补发报告生成，保留实际生成时间。"));
  }
  const columns = makeElement("div", "insight-columns");
  for (const [key, title] of [["changes", "值得留意的变化"], ["tensions", "还没得到确认的地方"]]) {
    const section = makeElement("section", "insight-section");
    section.append(makeElement("h4", "", title));
    for (const claim of note.analysis[key]) {
      section.append(makeElement("p", "", claim.text), evidenceDetails(claim.evidence_ids, note.evidence));
    }
    columns.append(section);
  }
  card.append(columns);
  const verification = makeElement("section", "verification");
  verification.append(makeElement("h4", "", "留给下一份晚报的问题"));
  const labels = { pending: "待验证", met: "条件满足", not_met: "条件未满足", unverifiable: "数据不足，无法验证" };
  if (!note.analysis.watchpoints.length) verification.append(makeElement("p", "", "当前材料没有可直接核对的指标。"));
  note.analysis.watchpoints.forEach((point, index) => {
    const metric = note.metrics[point.metric];
    const outcome = state.outcomes.find((item) => item.insight_id === note.id && item.watchpoint_index === index);
    const row = makeElement("div", "watchpoint");
    row.append(makeElement("span", `outcome-badge ${outcome?.status ?? "pending"}`, labels[outcome?.status ?? "pending"]),
      makeElement("p", "watch-question", point.question),
      makeElement("p", "watch-condition", `${metric.label} ${point.operator} ${point.threshold}${metric.unit}`));
    if (outcome?.report_id) {
      row.append(makeElement("p", "insight-meta", `核对 ${outcome.observed_date} 晚报${outcome.observed_value !== null ? `：${outcome.observed_value}${metric.unit}` : ""}`));
      if (outcome.evidence?.length) row.append(evidenceDetails(outcome.evidence_ids, outcome.evidence));
    }
    verification.append(row);
  });
  verification.append(makeElement("p", "insight-meta", "保留原判断，另记后续条件核对结果。"));
  card.append(verification);
  if (note.quality_warnings.length) {
    const quality = makeElement("details", "quality-notes");
    quality.append(makeElement("summary", "", `数据缺项与限制（${note.quality_warnings.length}）`));
    for (const warning of note.quality_warnings) quality.append(makeElement("p", "", warning));
    card.append(quality);
  }
  return card;
}

function renderInsights() {
  const notes = window.marketIntelUtils.selectVisibleInsights(state.insights, state.reports, state.date);
  document.querySelector("#insight-list").replaceChildren(...notes.map(renderInsight));
  const messages = {
    not_configured: "深度解读尚未启用，原始报告与简评可继续查看。",
    no_source_pair: "晨晚报材料尚未齐备，暂不生成深度解读。",
    unavailable: "本期深度解读暂时无法生成，已保留可核对的历史记录。",
    load_failed: "深度解读暂时无法读取，原始报告可继续查看。",
  };
  document.querySelector("#insight-status").textContent = messages[state.generation.status]
    ?? (notes.length ? "解读是基于下列材料的判断，展开依据可核对原文。" : "所选日期暂无深度解读。");
}

function renderHealth(health) {
  const box = document.querySelector("#data-health");
  if (!health) {
    box.textContent = "数据时效暂时无法核对，请查看原报告生成时间。";
    box.classList.add("is-delayed");
    return;
  }
  const delayed = window.marketIntelUtils.isHealthDelayed(health);
  box.classList.toggle("is-delayed", delayed);
  box.textContent = `数据目标 ${health.latest_target_date ?? "未提供"} · 原报告生成 ${timestampLabel(health.latest_source_generated_at)}（北京时间）。`
    + (delayed ? " 已较长时间未更新或有数据缺口，请结合交易日历核对。" : "")
    + (!health.pair_available ? " 晨晚报配对尚不完整。" : "");
}

async function optionalIndex(path, schema) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error("optional index unavailable");
  const payload = await response.json();
  if (payload.schema_version !== schema) throw new Error("unsupported optional index");
  return payload;
}

async function loadReports() {
  try {
    const response = await fetch("data/reports.json", { cache: "no-store" });
    if (!response.ok) throw new Error("report index unavailable");
    const data = await response.json();
    if (data.schema_version !== "market_intel_pages.reports.v1" || !Array.isArray(data.reports)) {
      throw new Error("unsupported report index");
    }
    state.reports = [...data.reports].sort((a, b) => b.date.localeCompare(a.date));
    const [insights, health, marketDaily] = await Promise.allSettled([
      optionalIndex("data/insights.json", "market_intel_pages.insights.v1"),
      optionalIndex("data/health.json", "market_intel_pages.health.v1"),
      fetch("data/market_daily_report.json", { cache: "no-store" }).then((response) => {
        if (!response.ok) throw new Error("market daily unavailable");
        return response.json();
      }),
    ]);
    renderMarketDaily(marketDaily.status === "fulfilled" ? marketDaily.value : null);
    if (insights.status === "fulfilled" && Array.isArray(insights.value.insights)) {
      state.insights = insights.value.insights;
      state.outcomes = insights.value.outcomes ?? [];
      state.generation = insights.value.generation ?? {};
    } else {
      state.generation = { status: "load_failed" };
    }
    renderHealth(health.status === "fulfilled" ? health.value : null);
    try {
      const summaryResponse = await fetch("data/daily_summaries.json", { cache: "no-store" });
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        if (summaryData.schema_version === "market_intel_pages.daily_summaries.v1"
          && Array.isArray(summaryData.summaries)) {
          state.summaries = summaryData.summaries;
        }
      }
    } catch {
      state.summaries = [];
    }
    populateDateFilter();
    const updated = new Date(data.generated_at);
    document.querySelector("#updated-at").textContent = `目录更新 ${new Intl.DateTimeFormat("zh-CN", {
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(updated)}`;
    render();
  } catch {
    loadError.hidden = false;
  }
}

for (const button of document.querySelectorAll(".filter")) {
  button.addEventListener("click", () => {
    state.kind = button.dataset.kind;
    for (const item of document.querySelectorAll(".filter")) {
      item.classList.toggle("is-active", item === button);
      item.setAttribute("aria-pressed", String(item === button));
    }
    render();
  });
}

dateFilter.addEventListener("change", (event) => {
  state.date = event.target.value;
  render();
});
document.querySelector("#clear-date").addEventListener("click", () => {
  state.date = "";
  dateFilter.value = "";
  render();
});

const themeToggle = document.querySelector("#theme-toggle");
const savedTheme = window.localStorage.getItem("market-intel-theme") ?? "system";
let activeTheme = window.marketIntelTheme.applyTheme(savedTheme);
function updateThemeButton() {
  const labels = { system: "系统", light: "浅色", dark: "深色" };
  themeToggle.textContent = `主题：${labels[activeTheme]}`;
  themeToggle.setAttribute("aria-label", `切换主题，当前为${labels[activeTheme]}`);
}
updateThemeButton();
themeToggle.addEventListener("click", () => {
  activeTheme = window.marketIntelTheme.nextTheme(activeTheme);
  window.marketIntelTheme.applyTheme(activeTheme);
  window.localStorage.setItem("market-intel-theme", activeTheme);
  updateThemeButton();
});

loadReports();
