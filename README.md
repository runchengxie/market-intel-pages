# Quant Market Intel

A static, read-only viewer for short daily market notes and their source reports. The public page and tracked report snapshot contain only the five most recent report dates. The complete source archive stays on the local machine outside this public repository.

## Local archive and public snapshot

When new report files are ready, add them to `data/reports.json` and `reports/`, then run:

```bash
python3 scripts/sync_public_snapshot.py \
  --archive-dir /home/richard/code/.research-data/quant-market-intel-archive
```

The command merges all reports and summaries into the specified local archive first, verifies their Markdown sources, then updates the tracked files to the five most recent report dates. Keep the archive path outside this repository; the repository is public. Existing public Git history is not rewritten, so previously pushed reports remain accessible through older commits.

To preview the current public snapshot locally:

```bash
python3 scripts/build_site.py --output /tmp/quant-market-intel-site
python3 -m http.server 8000 --directory /tmp/quant-market-intel-site
```

Then open <http://localhost:8000>.

## Data contract

`data/reports.json` contains a `reports` array. Each report has `id`, `date`, `kind` (`morning` or `evening`), `title`, `summary`, `sections`, and an optional `source_url` pointing to its Markdown copy under `reports/`.

`data/daily_summaries.json` contains a `summaries` array. Each summary has a report date, one short paragraph, the source morning/evening report IDs, a generation timestamp, a model label, and a prompt version. The page displays up to five report dates and renders report text as text, never HTML.

The GitHub Pages workflow runs `scripts/build_site.py` and publishes only the files referenced by the current five-day snapshot. When `MINIMAX_API_KEY` is configured as a repository Actions secret, it generates the newest note and merges the previous deployed five-day note history. Without the key or when MiniMax is unavailable, it keeps the existing notes and still deploys the page. The API key is never sent to the browser.

## Evidence-linked commentary and daily operations

The page also displays structured market commentary, paragraph-level source evidence, source timestamps, missing-data notes and observable conditions checked against a later evening report. Configure the repository secret `GEMINI_API_KEY` to enable generation. Optional repository variables: `GEMINI_MODEL` (default `gemini-2.5-flash`) and `INSIGHT_PROVIDER` (`gemini` or `minimax`). MiniMax uses its corresponding key/model settings. Provider failures leave reports available and show the commentary state explicitly.

`data/insights.json` uses `market_intel_pages.insights.v1`. Source hashes, prompt content/version and model identity govern cache reuse. Subsequent outcomes never replace the original commentary. Generated historical samples are labelled as replay. Local runs can persist immutable revisions outside the public repository with `--archive-dir`; Actions uploads a 90-day ledger artifact, which must be exported to permanent private storage for long-term retention.

The build writes `data/health.json` from **source report time**, not deployment time. Without an upstream calendar target it uses a conservative age warning, not a claim that every trading day is complete. Report imports require an explicit public manifest and preview by default; no script sends chat messages or enables production timers.

See [每日生成机制、迁移步骤与市场记忆](docs/daily-generation-options.md) for the measured pipeline gaps, scheme comparison, import commands, model comparison and MaiBot-inspired design boundaries.

Validation:

```bash
python3 -m unittest discover -s tests
node --test tests/*.cjs
node --check app.js
```
