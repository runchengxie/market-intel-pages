# Quant Market Intel MiniMax Summary Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one short daily market note from the newest eligible morning report and its preceding evening report during Pages publishing, while keeping publication successful if MiniMax is unavailable.

**Architecture:** A standalone Python script selects and validates the source pair, sends only those two reports to MiniMax's OpenAI-compatible text endpoint, validates the returned paragraph, and writes a daily-summary JSON record. The Pages workflow uses a GitHub Actions secret for the API key; when the key is unavailable or the call fails, it keeps historical summary records and the page shows “暂无简评” for the latest report date.

**Tech Stack:** Python 3 standard library, MiniMax OpenAI-compatible Chat Completions API, GitHub Actions secrets and variables.

**Spec:** `docs/superpowers/specs/2026-09-15-quant-market-intel-pages-design.md`

## Global Constraints

- Pair each morning report with the latest evening report generated earlier and dated on or before the morning report's target date.
- Send only the paired reports to the model and preserve their evidence and uncertainty.
- Generate roughly 40–80 Chinese characters with no title, list, boilerplate, unsupported claim, price target, or new trade instruction.
- Store `MINIMAX_API_KEY` only as a GitHub Actions secret; never expose it to the Pages browser or logs.
- Use the MiniMax OpenAI-compatible endpoint `https://api.minimaxi.com/v1/chat/completions`; take the model ID from `MINIMAX_MODEL` and default to `MiniMax-M2.7`.
- If the API is unavailable, publish the reports and historic summaries; never present an older summary as the latest report's summary.
- The default page feed contains up to five recent trading-day summaries; older dates remain only in the local archive and are not available through the public site.

---

### Task 1: Build and test source-pair selection and prompt assembly

**Files:**
- Create: `scripts/generate_daily_summary.py`
- Create: `prompts/daily-commentary-v1.md`
- Create: `tests/test_generate_daily_summary.py`

**Interfaces:**
- `select_source_pair(reports: list[dict]) -> tuple[dict, dict] | None` returns `(morning, evening)` or `None`.
- `build_messages(morning: dict, evening: dict, prompt: str) -> list[dict]` returns OpenAI-compatible system/user messages.
- Parse source generation times from each report's first section paragraph beginning `生成时间:`; reject candidates whose timestamp is later than the morning report.

- [ ] **Step 1: Write failing tests** for same-date reports, prior-date pairing across weekends, a later evening report being excluded, missing morning/evening halves, stable tie-breaking, and prompt contents. Use this record factory and assert shape:

```python
def report(report_id, date, kind, generated_at):
    return {
        "id": report_id, "date": date, "kind": kind,
        "sections": [{"title": "metadata", "paragraphs": [f"生成时间: {generated_at}"]}],
    }

def test_pairs_same_target_day_reports():
    evening = report("2026-09-14-evening", "2026-09-14", "evening", "2026-09-14 19:08")
    morning = report("2026-09-14-morning", "2026-09-14", "morning", "2026-09-15 07:03")
    self.assertEqual((morning, evening), select_source_pair([evening, morning]))
```

- [ ] **Step 2: Run the tests and confirm they fail** with `python3 -m unittest discover -s tests -p 'test_generate_daily_summary.py' -v`.

- [ ] **Step 3: Write `prompts/daily-commentary-v1.md`** with the approved voice: direct, colloquial, concise, no news-anchor tone, no generic transitions; preserve only supported claims, and state uncertainty rather than inventing an explanation or trade recommendation.

- [ ] **Step 4: Implement the pair selector and message builder** using `datetime.fromisoformat`, `json`, and the existing report sections. Normalize source timestamps from `YYYY-MM-DD HH:MM` by replacing the separator with `T` and attaching `+08:00`. Select the latest morning by target date and generation time; among evenings with `date <= morning.date` and `generated_at < morning.generated_at`, select the latest generation time.

- [ ] **Step 5: Re-run the tests** with `python3 -m unittest discover -s tests -p 'test_generate_daily_summary.py' -v` and verify the actual 2026-09-14 pair selects `2026-09-14-evening` and `2026-09-14-morning`.

- [ ] **Step 6: Commit** as `feat: select paired reports for daily notes`.

### Task 2: Call MiniMax securely and validate the response

**Files:**
- Modify: `scripts/generate_daily_summary.py`
- Modify: `tests/test_generate_daily_summary.py`
- Modify: `prompts/daily-commentary-v1.md`

**Interfaces:**
- `generate_summary(messages: list[dict], api_key: str, model: str) -> str` posts to `https://api.minimaxi.com/v1/chat/completions` with `Authorization: Bearer <key>` and JSON body `{ "model": model, "messages": messages, "temperature": 0.4, "max_completion_tokens": 300 }`.
- `validate_summary(text: str) -> str` strips whitespace and any `<think>...</think>` block, rejects empty output, markdown headings/lists, and output longer than 120 Unicode characters.
- `MINIMAX_API_KEY` is required for generation; `MINIMAX_MODEL` defaults to `MiniMax-M2.7`.

- [ ] **Step 1: Write failing HTTP-mock tests** for valid response parsing, MiniMax `<think>` removal, timeout, non-2xx status, invalid JSON, empty response, heading/list output, and overlong output. Assert the bearer key is supplied only as a request header.

- [ ] **Step 2: Run the tests and confirm they fail** with `python3 -m unittest discover -s tests -p 'test_generate_daily_summary.py' -v`.

- [ ] **Step 3: Implement the HTTPS call** with `urllib.request`, JSON encoding, a 30-second timeout, and no printing of request headers, full response bodies, or API errors that could include secret material. Construct the request as follows:

```python
body = json.dumps({
    "model": model,
    "messages": messages,
    "temperature": 0.4,
    "max_completion_tokens": 300,
}).encode("utf-8")
request = urllib.request.Request(
    "https://api.minimaxi.com/v1/chat/completions",
    data=body,
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=30) as response:
    payload = json.loads(response.read())
text = payload["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Implement response validation** against the `choices[0].message.content` field; reject invalid or overlong content so it cannot be published as a daily note.

- [ ] **Step 5: Re-run all generator tests** with `python3 -m unittest discover -s tests -p 'test_generate_daily_summary.py' -v` and inspect logs from a mocked failure to confirm they contain the error category but no credential or report text.

- [ ] **Step 6: Commit** as `feat: generate daily notes with MiniMax`.

### Task 3: Preserve history and make generation failure non-blocking

**Files:**
- Modify: `scripts/generate_daily_summary.py`
- Modify: `tests/test_generate_daily_summary.py`

**Interfaces:**
- CLI: `python3 scripts/generate_daily_summary.py --reports data/reports.json --summaries data/daily_summaries.json --output _site/data/daily_summaries.json`.
- Output uses schema `market_intel_pages.daily_summaries.v1` and records `date`, `text`, `morning_report_id`, `evening_report_id`, `generated_at`, `model`, and `prompt_version`.
- On missing key, no valid pair, or provider failure, copy historical records to output, print one non-sensitive status line, and exit 0. Do not add a record for the new date.
- If an existing record references the same morning/evening IDs, reuse it and do not incur a second model call unless `--force` is passed.

- [ ] **Step 1: Write failing tests** for history preservation on success/failure, pair-ID idempotency, forced regeneration, and no new record on missing credentials/provider failure.

- [ ] **Step 2: Run tests and confirm they fail** with `python3 -m unittest discover -s tests -p 'test_generate_daily_summary.py' -v`.

- [ ] **Step 3: Implement output merging** so a successful call replaces only the summary for the same source pair and retains older summaries; failures retain the input history unchanged. Merge by source-pair identity, not by date alone:

```python
pair_ids = (record["morning_report_id"], record["evening_report_id"])
history = [item for item in history if
           (item["morning_report_id"], item["evening_report_id"]) != pair_ids]
history.append(record)
```

- [ ] **Step 4: Re-run tests** with `python3 -m unittest discover -s tests -p 'test_generate_daily_summary.py' -v` and verify a failed latest call does not change the existing historic summary fixture or cause an older paragraph to be selected for the latest morning report.

- [ ] **Step 5: Commit** as `fix: keep summary history when generation fails`.

### Task 4: Integrate generation into Pages publishing

**Files:**
- Modify: `.github/workflows/deploy-pages.yml`
- Modify: `scripts/build_site.py`
- Modify: `tests/test_build_site.py`

**Interfaces:**
- The Pages workflow invokes the generator before `scripts/build_site.py`; the build uses the generated output when present and otherwise uses committed history.
- Workflow environment maps `MINIMAX_API_KEY` from the GitHub Actions secret and `MINIMAX_MODEL` from a repository variable or the script default.
- A `workflow_dispatch` boolean input `force_summary` maps to `--force` for deliberate re-generation.

- [ ] **Step 1: Add an integration test** that runs the artifact builder with a generated summary file and with only historic summaries, confirming both produce a valid site.

- [ ] **Step 2: Update the workflow** to call the generator before building the site and pass the secret through the process environment only. Keep deployment dependent on successful artifact generation, but let the generator's documented provider-failure path exit successfully. Pass credentials using the job step environment, never a command argument:

```yaml
env:
  MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}
  MINIMAX_MODEL: ${{ vars.MINIMAX_MODEL }}
run: python3 scripts/generate_daily_summary.py --reports data/reports.json --summaries data/daily_summaries.json --output _site/data/daily_summaries.json
```

- [ ] **Step 3: Run all tests and local artifact checks** with `python3 -m unittest discover -s tests -v`, the build command, and `git diff --check`.

- [ ] **Step 4: Commit** as `ci: generate daily market notes before publishing`.

### Task 5: Configure and verify MiniMax after merge

**Files:**
- GitHub Actions secret: `MINIMAX_API_KEY`
- Optional GitHub Actions variable: `MINIMAX_MODEL`

- [ ] **Step 1: Add the API key as a repository Actions secret** in GitHub settings; do not put the key in a command, issue, file, workflow log, or Git commit.

- [ ] **Step 2: Set `MINIMAX_MODEL`** to an enabled model ID if the default is not desired.

- [ ] **Step 3: Run the workflow manually** against the current report index and verify the published paragraph references the expected report date and paired source IDs.

- [ ] **Step 4: Verify the no-secret path** by running the workflow without the secret in a safe branch context; it should publish the viewer and five-day summary snapshot with “暂无简评” for an ungenerated current pair. The full archive remains outside the Pages artifact.

## Verification checklist

- `python3 -m unittest discover -s tests -v` passes without network access.
- Pair selection handles same-day, weekend, missing-data, and timestamp-order cases.
- Mock provider tests cover successful and failed API responses without logging credentials.
- The output record points to exactly the two source report IDs used by the prompt.
- Missing credentials/provider failure keeps publication live and does not create a stale latest-day summary.
- The `MINIMAX_API_KEY` exists only as an Actions secret and never appears in browser assets or committed files.

## Provider reference

MiniMax's official documentation describes the OpenAI-compatible endpoint, Bearer authorization, Chat Completions request and current model identifiers: <https://platform.minimaxi.com/docs/api-reference/text-chat-openai>.
