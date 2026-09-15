# Quant Market Intel Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebrand the static report site as Quant Market Intel, publish only the five most recent trading days, and preserve the full report archive outside the public repository on the local machine.

**Architecture:** A local Python standard-library sync command merges the current report snapshot into an archive directory outside the repository, then trims the tracked public snapshot to the latest five trading dates. A build script validates that snapshot and assembles the Pages artifact; the vanilla JavaScript viewer presents five daily notes and their source reports.

**Tech Stack:** HTML, CSS, vanilla JavaScript, Python 3 standard library, GitHub Actions Pages.

**Spec:** `docs/superpowers/specs/2026-09-15-quant-market-intel-pages-design.md`

## Global Constraints

- Pair each morning report with the latest earlier evening report dated on or before that morning report's target date.
- Keep generated commentary to roughly 40–80 Chinese characters, with no title, list, boilerplate, unsupported claim, price target, or new trade instruction.
- Keep all source reports indefinitely in a local archive path passed to the sync command; never copy that archive into Git or Pages.
- Keep at most the latest five distinct dates with morning reports in the tracked public snapshot and Pages artifact.
- Do not rewrite existing public Git history; older reports already pushed remain visible through prior commits.
- Never put model credentials in browser code or committed files.
- Preserve report filters, date selection, original report content, and safe text rendering.

---

### Task 1: Add the summary data contract and reviewed sample

**Files:**
- Create: `data/daily_summaries.json`
- Create: `tests/test_build_site.py`
- Create: `scripts/build_site.py`
- Create: `scripts/sync_public_snapshot.py`

**Interfaces:**
- Summary file schema: `{ "schema_version": "market_intel_pages.daily_summaries.v1", "summaries": [...] }`.
- Each summary record has `date`, `text`, `morning_report_id`, `evening_report_id`, `generated_at`, `model`, and `prompt_version`.
- `sync_public_snapshot.sync_snapshot(root: Path, archive_dir: Path) -> None` merges report/summary data and referenced Markdown into a full local archive, then limits the repository's current snapshot to the latest five trading dates.
- `build_site.build_site(root: Path, output: Path, summaries_path: Path) -> None` validates references and copies only the public snapshot to `output`.

- [ ] **Step 1: Write failing tests** in `tests/test_build_site.py` for local archive merge, idempotent report IDs, preserving source files before snapshot pruning, limiting the tracked snapshot to five trading dates, missing summary source IDs, and exclusion of unreferenced Markdown from `_site`. Use six dates, each with a morning and evening report; assert the external archive retains all 12 records while the public snapshot/artifact retain only the latest 10.

```python
def write_summary_fixture(directory, morning_report_id):
    record = {
        "date": "2026-09-14", "text": "sample", "morning_report_id": morning_report_id,
        "evening_report_id": "2026-09-14-evening", "generated_at": "2026-09-15T07:30:00+08:00",
        "model": "test", "prompt_version": "daily-note-v1",
    }
    path = directory / "summaries.json"
    path.write_text(json.dumps({"schema_version": SUMMARY_SCHEMA, "summaries": [record]}))
    return path

class BuildSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.output = self.directory / "site"

    def test_keeps_all_indexed_reports(self):
        build_site(REPO_ROOT, self.output, REPO_ROOT / "data/daily_summaries.json")
        data = json.loads((self.output / "data/reports.json").read_text())
        self.assertEqual(4, len(data["reports"]))

    def test_rejects_unknown_summary_source(self):
        summaries = write_summary_fixture(self.directory, morning_report_id="missing-morning")
        with self.assertRaisesRegex(ValueError, "source report"):
            build_site(REPO_ROOT, self.output, summaries)
```

- [ ] **Step 2: Run the tests and confirm they fail** with `python3 -m unittest discover -s tests -v`.

- [ ] **Step 3: Add the reviewed 2026-09-14 note** using source IDs `2026-09-14-morning` and `2026-09-14-evening` and the exact sample from the spec. Keep the model value `chatgpt-reviewed` and prompt version `daily-note-v1` so the record does not imply it came from MiniMax.

- [ ] **Step 4: Implement `sync_public_snapshot.py`** using only `json`, `pathlib`, `shutil`, and `argparse`. Merge reports by `id` and summaries by `(morning_report_id, evening_report_id)`, copy Markdown into `<archive-dir>/reports/`, and write complete `reports.json` and `daily_summaries.json` indexes under `<archive-dir>/data/`. Verify that every archived Markdown reference exists before pruning. Then rewrite the repository indexes with records from the latest five distinct dates that have morning reports, copy those Markdown files back into the repository, and remove only now-unreferenced Markdown from the managed repository `reports/` directory. Require an explicit `--archive-dir` path outside the repository.

- [ ] **Step 5: Implement `build_site.py`** using only `json`, `pathlib`, `shutil`, and `argparse`. Validate both JSON schemas and every summary's source IDs/kinds/date, reject a public snapshot spanning more than five morning-report dates, copy `index.html`, `app.js`, `styles.css`, indexed reports, and `daily_summaries.json`, and include only referenced Markdown. The validation core should follow this structure:

```python
by_id = {report["id"]: report for report in report_data["reports"]}
for summary in summary_data["summaries"]:
    morning = by_id.get(summary["morning_report_id"])
    evening = by_id.get(summary["evening_report_id"])
    if not morning or not evening:
        raise ValueError("summary source report is missing")
    if morning["kind"] != "morning" or evening["kind"] != "evening":
        raise ValueError("summary source report kind is invalid")
    if summary["date"] != morning["date"]:
        raise ValueError("summary date must match its morning report")
```

- [ ] **Step 6: Re-run the tests and inspect the artifact** with `python3 -m unittest discover -s tests -v`, using a temporary archive path, and `python3 scripts/build_site.py --output /tmp/quant-market-intel-site`; confirm the local archive keeps all fixture dates while the artifact keeps only the latest five.

- [ ] **Step 7: Commit** the tested archive and snapshot pipeline as `feat: keep full report archive locally`.

### Task 2: Present the daily note and apply Quant branding

**Files:**
- Modify: `index.html`
- Modify: `app.js`
- Modify: `styles.css`
- Modify: `README.md`

**Interfaces:**
- `state.summaries` stores validated summary records loaded from `data/daily_summaries.json`.
- `renderDailySummaries(date)` displays the selected date's summary when a date is selected, or up to five most recent distinct summary dates that have valid morning reports when no date is selected. It never substitutes an older summary for a missing newer date.
- `visibleReports()` displays reports for the selected date, or only the latest available report date when no date is selected.

- [ ] **Step 1: Add the summary card markup and update branding** in `index.html` to “Quant Market Intel” / “Quant 市场情报”; update document title, description, accessible labels, wordmark, and footer.

- [ ] **Step 2: Load summaries and implement date selection** in `app.js`. Validate the schema and source IDs before rendering; keep rendering all content with `textContent` and DOM element creation. Preserve the current report filters and date filter. The selection behavior should follow this exact rule:

```js
function renderDailySummaries(date) {
  const dates = date
    ? [date]
    : [...new Set(state.summaries.map((item) => item.date))]
        .filter((itemDate) => state.reports.some((report) => report.date === itemDate && report.kind === "morning"))
        .sort((a, b) => b.localeCompare(a))
        .slice(0, 5);
  summaryList.replaceChildren(...dates.map((targetDate) => renderSummaryCard(
    state.summaries.find((item) => item.date === targetDate), targetDate,
  )));
  summaryEmpty.hidden = dates.length !== 0;
}
```

- [ ] **Step 3: Add restrained summary-card styles** in `styles.css` that fit the current layout and remain readable on narrow screens.

- [ ] **Step 4: Update the README** with the new name, local preview command, explicit `--archive-dir` sync command, local full-history policy, five-trading-day public limit, and report-generation status (static data until the MiniMax plan is implemented).

- [ ] **Step 5: Run local checks** with the build tests, `git diff --check`, and `python3 -m http.server 8000` followed by manual verification of the default note, selected-date behavior, “暂无简评”, report-type filters, and safe rendering.

- [ ] **Step 6: Commit** as `feat: show concise daily market notes`.

### Task 3: Build and publish the complete archive

**Files:**
- Modify: `.github/workflows/deploy-pages.yml`
- Modify: `tests/test_build_site.py`
- Modify: `scripts/build_site.py`

**Interfaces:**
- `python3 scripts/build_site.py --output _site` is the single artifact build command used locally and in GitHub Actions.
- The workflow uploads only `_site`; source data stays in the repository.

- [ ] **Step 1: Add a workflow/build integration test** that asserts `_site` contains the summary JSON, complete report index, and only Markdown files referenced by that index.

- [ ] **Step 2: Change the Pages workflow** to run Python 3, run `python3 scripts/build_site.py --output _site`, then upload `_site` instead of manually copying files. Remove the old manual `mkdir`/`cp` artifact commands.

- [ ] **Step 3: Run the complete local verification** with `python3 -m unittest discover -s tests -v`, `python3 scripts/build_site.py --output /tmp/quant-market-intel-site`, JSON parsing of every generated data file, and `git diff --check`.

- [ ] **Step 4: Commit** as `ci: build the Quant Market Intel Pages artifact`.

### Task 4: Rename the GitHub repository after code review

**Files:**
- GitHub repository setting: `runchengxie/market-intel-pages` → `runchengxie/quant-market-intel-pages`
- Local checkout remote configuration after the GitHub rename

- [ ] **Step 1: After the code PR is merged, rename the repository through GitHub settings or the authenticated GitHub CLI.** Do not rename it before the reviewed code is merged.

- [ ] **Step 2: Update the local remote URL** to `https://github.com/runchengxie/quant-market-intel-pages.git` and confirm the old URL redirects.

- [ ] **Step 3: Verify the GitHub Pages deployment URL** and confirm the site, index, summary data, and source Markdown all load after the repository rename.

## Verification checklist

- `python3 -m unittest discover -s tests -v` passes.
- `python3 scripts/build_site.py --output /tmp/quant-market-intel-site` succeeds and retains every indexed report.
- The short note is based on the correct morning/evening IDs and selected-date behavior never shows stale copy as current.
- No report body or model output is interpreted as HTML.
- The local archive retains every report; the current repository snapshot and Pages artifact contain at most five trading dates.
- The Pages artifact contains no unreferenced Markdown and no older report data.
- The renamed Pages deployment loads successfully after the repository setting change.
