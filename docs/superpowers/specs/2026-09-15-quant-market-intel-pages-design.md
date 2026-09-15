# Quant Market Intel Pages Design

## Goal

Turn the existing market report viewer into a concise daily market-intelligence page. Each daily note should synthesize the latest morning report and the immediately preceding evening report into one short, natural paragraph, while keeping the source reports available for context. Align the product name with the Quant product family and set a clear public-page retention window.

## Current state

- The repository is a static GitHub Pages site. Its current branding is “Market Intel” / “市场简报”.
- `data/reports.json` contains the report index and report bodies; full Markdown files are also copied into the deployed site.
- The current Pages workflow only copies repository files into the deployment artifact. It does not fetch reports, call a model, or apply retention.
- The current index is about 32 KB, the whole checkout about 672 KB, and it has four sample reports. A 30-day window is negligible at this scale.
- The 2026-09-14 pair demonstrates the desired timing: the evening edition and the next morning's edition share a report date. The morning report was generated at 07:03 on 2026-09-15 and carries the 2026-09-14 target date.

## User experience

- Rename the product branding to “Quant Market Intel” / “Quant 市场情报”. Use `quant-market-intel-pages` as the intended repository name so it is recognizable within the Quant product family.
- Put a single-paragraph daily commentary near the top of the page. Keep the existing morning and evening reports below it as expandable source material.
- Keep the existing date and report-type navigation for archive browsing.
- Show a clear “暂无简评” state when a valid morning/evening pair is unavailable; do not fabricate a note from only one half of the intended input window.
- Keep reports dated within the most recent 30 calendar days in the public Pages artifact. Older files may remain in Git history for repository continuity; retention applies to the deployed public artifact, not Git history.
- Evaluate the window using the report target date in `Asia/Shanghai`: retain dates from today minus 29 days through today, inclusive.

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
- Build the Pages artifact from records in the 30-day window. Include only Markdown files referenced by the retained report index and summary records.
- Keep source reports in the repository unless an explicit repository-level deletion policy is later approved. This avoids rewriting Git history and keeps the existing report archive recoverable.
- The current repository has no report-ingestion or model-calling workflow. The first implementation should work from committed report records and add a publishing-time generation step only after the MiniMax secret and endpoint are configured. The site must remain usable with summaries absent.

## Rename and deployment implications

- Update page title, metadata, wordmark, README, and workflow references to the Quant Market Intel name.
- Rename the GitHub repository to `quant-market-intel-pages` as a repository setting change after the code change is reviewed. Confirm GitHub's old-URL redirect and update local remotes after the rename.
- Keep the existing GitHub Pages deployment target unless the repository rename requires a Pages setting adjustment; verify the published URL after the rename.

## Acceptance criteria

1. The first page view presents at most one short daily commentary, visibly associated with its report date and built from the correct morning/evening pair.
2. A weekend/holiday with no same-day evening report uses the most recent preceding evening report; absence of either source produces no generated paragraph.
3. Commentary includes no factual claim absent from its source pair and has no browser-visible model credentials.
4. Public artifacts contain no report older than 30 calendar days and do not include unreferenced Markdown copies.
5. Existing report filters, date selection, original report content, and safe text rendering continue to work.
6. The page and repository documentation use the Quant Market Intel branding; the renamed Pages deployment loads successfully.
7. Model failure leaves the rest of the report viewer available and does not carry forward stale generated text.

## Open implementation detail

The final model call should be added only after confirming the MiniMax API endpoint, model name, and GitHub Actions secret name. The local repository currently has no provider settings. Until then, the user-reviewed daily summary is stored as static data and the site degrades cleanly when none exists.
