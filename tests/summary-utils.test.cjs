const test = require("node:test");
const assert = require("node:assert/strict");
const { selectVisibleSummaries, selectVisibleReports } = require("../summary-utils.js");
const { selectVisibleInsights } = require("../summary-utils.js");

function report(date, kind) {
  return { id: `${date}-${kind}`, date, kind };
}

function note(date, eveningDate = date) {
  return {
    date,
    text: `note ${date}`,
    morning_report_id: `${date}-morning`,
    evening_report_id: `${eveningDate}-evening`,
  };
}

test("insight navigation excludes missing source reports", () => {
  const reports = [report("2026-09-14", "morning"), report("2026-09-14", "evening")];
  const records = [
    { ...note("2026-09-14"), source_report_ids: ["2026-09-14-morning", "2026-09-14-evening"] },
    { ...note("2026-09-14"), source_report_ids: ["missing"] },
  ];
  assert.deepEqual(selectVisibleInsights(records, reports, ""), [records[0]]);
});

test("default view returns summaries for at most five latest report dates", () => {
  const reports = [];
  const summaries = [];
  for (let day = 1; day <= 7; day += 1) {
    const date = `2026-09-${String(day).padStart(2, "0")}`;
    reports.push(report(date, "morning"), report(date, "evening"));
    summaries.push(note(date));
  }

  const visible = selectVisibleSummaries(summaries, reports, "");

  assert.deepEqual(visible.map((item) => item.date), [
    "2026-09-07", "2026-09-06", "2026-09-05", "2026-09-04", "2026-09-03",
  ]);
});

test("selected date returns only its summary", () => {
  const reports = [report("2026-09-14", "morning"), report("2026-09-14", "evening")];
  const summaries = [note("2026-09-14"), note("2026-09-13")];

  assert.deepEqual(
    selectVisibleSummaries(summaries, reports, "2026-09-14").map((item) => item.date),
    ["2026-09-14"],
  );
});

test("summary with missing or incorrectly typed sources is not displayed", () => {
  const reports = [report("2026-09-14", "morning"), report("2026-09-14", "evening")];
  const invalid = [
    { ...note("2026-09-14"), evening_report_id: "missing-evening" },
    { ...note("2026-09-14"), morning_report_id: "2026-09-14-evening" },
  ];

  assert.deepEqual(selectVisibleSummaries(invalid, reports, ""), []);
});

test("default report list contains only the latest date", () => {
  const reports = [
    report("2026-09-13", "morning"),
    report("2026-09-14", "morning"),
    report("2026-09-14", "evening"),
  ];

  assert.deepEqual(
    selectVisibleReports(reports, "", "all").map((item) => item.id),
    ["2026-09-14-morning", "2026-09-14-evening"],
  );
});

test("selected date and kind filter apply together", () => {
  const reports = [
    report("2026-09-13", "morning"),
    report("2026-09-14", "morning"),
    report("2026-09-14", "evening"),
  ];

  assert.deepEqual(
    selectVisibleReports(reports, "2026-09-14", "morning").map((item) => item.id),
    ["2026-09-14-morning"],
  );
});
