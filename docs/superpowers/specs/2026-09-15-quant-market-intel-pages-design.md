# Quant Market Intel Pages Design

## Goal

Turn the existing market report viewer into a concise daily market-intelligence page. Each daily note should synthesize the latest morning report and the immediately preceding evening report into one short, natural paragraph. Keep the full report archive on the local machine, while publishing only the five most recent trading days to the website. Align the product name with the Quant product family.

## Current state

- The repository is a static GitHub Pages site. Its current branding is “Market Intel” / “市场简报”.
- `data/reports.json` contains the report index and report bodies; full Markdown files are also copied into the deployed site.
- The current Pages workflow only copies repository files into the deployment artifact. It does not fetch reports, call a model, or apply retention.
- The current index is 32,810 bytes, the four linked Markdown files total 22,899 bytes, and the whole checkout is about 672 KB.
- At two reports per day, the observed averages project to about 10.2 MB/year for index plus Markdown (roughly 9.7 MiB). With 30% growth headroom and the current site shell, expect about 13–14 MB/year. Daily summary records add little. This estimate uses four reports, so treat it as a planning estimate, not a guaranteed ceiling.
- The GitHub repository is public, so tracked report files and Git history are public. Full local archive data must be stored outside the repository; the current public snapshot can contain only the recent five trading days.
- The 2026-09-14 pair demonstrates the desired timing: the evening edition and the next morning's edition share a report date. The morning report was generated at 07:03 on 2026-09-15 and carries the 2026-09-14 target date.

## User experience

- Rename the product branding to “Quant Market Intel” / “Quant 市场情报”. Use `quant-market-intel-pages` as the intended repository name so it is recognizable within the Quant product family.
- By default, show concise daily notes for the five most recent trading days, newest first. Each note is one paragraph and associated with its report date.
- Show source morning/evening reports for those five trading days, with details remaining expandable. The date selector only offers dates in this public five-day window.
- Retain the complete archive locally outside the repository, at a path supplied to the local archive/snapshot command. Never copy that archive into the public Pages artifact.
- Keep the existing report-type navigation within the public five-day window.
- Show a clear “暂无简评” state when a valid morning/evening pair is unavailable; do not fabricate a note from only one half of the intended input window.
- Keep all reports locally without an automatic expiry. Publish only the latest five distinct report dates, counting a date even if it currently has only an evening report.
- Do not rewrite existing public Git history. Older reports already pushed remain accessible through prior public commits; future deployments and current repository snapshots expose only the latest five trading dates.

## Pairing and summary generation

- Pair a morning report with the latest evening report whose report date is the same as or earlier than the morning report's target date. Use report timestamps as a tie-breaker if multiple candidates exist. This handles weekends and holidays without assuming that the previous calendar date has a report.
- Generate one paragraph of roughly 40–80 Chinese characters, with no title, bullet list, or boilerplate. Prefer the consequential overnight change, cross-market strength/weakness, and one relevant uncertainty or watch point.
- Preserve only claims supported by the two reports. Do not add price targets, trade instructions, catalysts, or causal explanations that are absent from the inputs. Retain cautious wording when data is stale, degraded, or contradictory.
- Prototype the prompt against the existing 2026-09-14 report pair using ChatGPT-assisted generation and save the result as a reviewed fixture. Once the style and factual checks are accepted, automate generation with MiniMax in the publishing workflow. The API key must be a GitHub Actions secret and must never enter browser code or committed files.
- If model generation fails, publish the reports and show “暂无简评”; the report deployment itself should not fail. Do not silently reuse yesterday's commentary as today's.

### First style sample

Using the 2026-09-14 evening report and the following morning report:

> A股个股面还行，指数没跟上，成交也偏弱。隔夜半导体明显转弱，SMH跌4.75%、AMD跌4.4%，日韩芯片股也普遍回落，科技硬件先看卖压能不能缓下来。

This is a prompt-calibration sample, not a deterministic template. The model should vary wording naturally while preserving the facts and uncertainty from the paired reports.

## Data model and publishing

- Add a daily-summary record with a stable date, generated text, the source morning and evening report IDs, generation timestamp, and model/prompt version.
- A local snapshot command merges current report files into an archive directory outside the repository, then writes the latest five distinct report-date snapshot back to `data/reports.json`, `data/daily_summaries.json`, and `reports/` for publication. It must archive and verify files before removing older report files from the repository worktree.
- Build the Pages artifact from that five-day public snapshot and copy only Markdown files referenced by the snapshot.
- The current repository has no report-ingestion or model-calling workflow. The first implementation should work from committed report records and add a publishing-time generation step only after the MiniMax secret is configured. The site must remain usable with summaries absent.

## Rename and deployment implications

- Update page title, metadata, wordmark, README, and workflow references to the Quant Market Intel name.
- Rename the GitHub repository to `quant-market-intel-pages` as a repository setting change after the code change is reviewed. Confirm GitHub's old-URL redirect and update local remotes after the rename.
- Keep the existing GitHub Pages deployment target unless the repository rename requires a Pages setting adjustment; verify the published URL after the rename.

## Acceptance criteria

1. The first page view presents up to five short daily commentaries for the most recent trading days, newest first, each built from the correct morning/evening pair and visibly associated with its report date.
2. A weekend/holiday with no same-day evening report uses the most recent preceding evening report; absence of either source produces no generated paragraph.
3. Commentary includes no factual claim absent from its source pair and has no browser-visible model credentials.
4. The public artifact and current tracked report snapshot contain no more than the latest five trading dates; all older source reports remain in the local archive outside the repository.
5. Existing report filters, date selection, original report content, and safe text rendering continue to work.
6. The page and repository documentation use the Quant Market Intel branding; the renamed Pages deployment loads successfully.
7. Model failure leaves the rest of the report viewer available and does not carry forward stale generated text.
8. The date selector offers only dates in the public five-day window; older reports remain available in the local archive.

## Open implementation detail

The MiniMax endpoint and model default have been checked against the provider's current official API documentation. The remaining runtime setup is the GitHub Actions `MINIMAX_API_KEY` secret. Until it is configured, the user-reviewed daily summary is stored as static data and the site degrades cleanly when none exists.

The estimated annual volume is modest, but the user prefers local full-history retention and a short public page. Existing public Git history is not rewritten; deleting old data from the current branch and Pages cannot remove copies already present in earlier public commits.
