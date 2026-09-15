# Market Intel Pages

A public, static, read-only report viewer for market-intel outputs. It currently
contains local reports through 2026-09-14.

## Preview locally

From this directory, run:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Data contract

`data/reports.json` is the index consumed by the page. It contains a
`reports` array. Each report has `id`, `date`, `kind` (`morning` or `evening`),
`title`, `summary`, `sections`, and an optional `source_url` pointing to its
full Markdown copy under `reports/`. A section has a `title` and `paragraphs`.
All report text is inserted as text, never interpreted as HTML.

The Pages workflow publishes the viewer, index, and Markdown copies. Update
these report files when new local outputs are ready. Do not add raw collection
data, run manifests, local file paths, or credentials to this public repository.
The viewer does not fetch data from market providers or contain credentials.
