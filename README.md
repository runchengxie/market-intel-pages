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

The GitHub Pages workflow runs `scripts/build_site.py` and publishes only the files referenced by the current five-day snapshot. It does not fetch market data or contain credentials. Until MiniMax generation is configured, daily notes are reviewed static records.
