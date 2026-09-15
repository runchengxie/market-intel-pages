# Market Intel Pages

A static, read-only report viewer for market-intel outputs. The current data is
synthetic demo content; do not publish production reports until their public
release scope has been reviewed.

## Preview locally

From this directory, run:

```bash
python3 -m http.server 8000
```

Then open <http://localhost:8000>.

## Data contract

`data/reports.json` is the only input consumed by the page. It contains a
`reports` array. Each report has `id`, `date`, `kind` (`morning` or `evening`),
`title`, `summary`, and `sections`. A section has a `title` and `paragraphs`.
All report text is inserted as text, never interpreted as HTML.

The planned publisher can transform local report artifacts into this small
static contract. It should publish only explicitly approved sections and their
associated images. The viewer does not fetch data from market providers or
contain credentials.
