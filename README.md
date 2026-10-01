# Quant Market Intel Pages

Daily reporting has moved to `quant-intel-platform`. This repository preserves the legacy pages, historical reports, and rollback entry point. It is no longer a target for new daily-report features.

[中文 README](README.zh-CN.md)

[Open the new reports](https://runchengxie.github.io/quant-intel-platform/) · [View the legacy archive](https://runchengxie.github.io/quant-intel-pages/?legacy=1)

## What remains here

- Legacy Astro pages under `src/` and the `/legacy/` fallback.
- Reviewed public report and data snapshots under `artifacts/public/`.
- Import, generation, validation, and build scripts under `scripts/` and `prompts/`.
- Documentation for maintenance, data contracts, and historical design decisions.

The site remains published as a compatibility archive while maintained links, historical report access, or rollback procedures still depend on it. Retirement is a separate owner decision, not a date-based cleanup. Before retiring the live site, verify that the replacement covers required historical URLs and snapshots, maintained links and downloads have been redirected or intentionally preserved, deployment and recovery procedures no longer depend on this repository, and the archive can still be recovered from its immutable Git history. Review these gates in [archive lifecycle](docs/archive-lifecycle.md); do not delete history as part of ordinary feature work.

The 07:00 and 19:00 publication targets use Beijing time. They are targets rather than guarantees. Readers should use the displayed generation time, observation date, and data status to judge freshness.

## Local preview

Requirements: Python 3.11, Node.js 24, and npm.

```bash
npm ci
preview_root=$(mktemp -d /tmp/qmi-preview.XXXXXX)
python3 scripts/build_site.py --output "$preview_root/quant-intel-pages"
python3 -m http.server 8000 --directory "$preview_root"
```

Open `http://localhost:8000/quant-intel-pages/`. The build output is created in the temporary directory. Use `npm run build` when checking the Astro pages only.

Production publishing and scheduled jobs belong to `quant-intel-deploy`. Historical import, snapshot, and model scripts remain for rollback and compatibility review. They do not receive new production report features.
