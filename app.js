const state = {
  reports: [],
  summaries: [],
  kind: "all",
  date: "",
};

const reportList = document.querySelector("#report-list");
const emptyState = document.querySelector("#empty-state");
const loadError = document.querySelector("#load-error");
const summaryList = document.querySelector("#daily-summary-list");
const summaryEmpty = document.querySelector("#summary-empty");
const dateFilter = document.querySelector("#date-filter");

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
  const head = makeElement("div", "report-meta");
  const kind = report.kind === "morning" ? "晨报" : "晚报";
  head.append(
    makeElement("span", "report-type", kind),
    makeElement("time", "report-date", dateLabel(report.date)),
  );
  article.append(head, makeElement("h3", "report-title", report.title));
  article.append(makeElement("p", "report-summary", report.summary));

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
  if (report.source_url) {
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

async function loadReports() {
  try {
    const response = await fetch("data/reports.json", { cache: "no-store" });
    if (!response.ok) throw new Error("report index unavailable");
    const data = await response.json();
    if (data.schema_version !== "market_intel_pages.reports.v1" || !Array.isArray(data.reports)) {
      throw new Error("unsupported report index");
    }
    state.reports = [...data.reports].sort((a, b) => b.date.localeCompare(a.date));
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

loadReports();
