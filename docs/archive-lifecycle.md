# Legacy archive lifecycle

`quant-intel-pages` remains the compatibility site for historical reports and the rollback entry point after daily reporting moved to `quant-intel-platform`. The archive is still useful while readers, maintained links, or recovery procedures depend on it.

## Retirement gates

The repository owner may propose retiring the live Pages deployment after all of these conditions are checked:

1. Required historical reports, snapshots, and downloads are available at a documented replacement URL, or are explicitly designated as archive-only with a durable access path.
2. Maintained links in the new report site, project documentation, and deployment configuration have been redirected or intentionally kept pointed at the archive.
3. No production scheduler, release, rollback, or recovery runbook requires the live legacy site.
4. The archive can be reconstructed from its immutable Git history, and the proposed replacement or archival URL has been verified.
5. The owner records the decision, the URLs that remain supported, and the recovery procedure in a dated maintenance record.

Retirement may mean stopping the live Pages deployment while retaining the repository and Git history. It does not imply deleting snapshots, rewriting history, or removing redirects. Those are separate changes and require their own impact review. Until the gates are met and recorded, keep the current archive and rollback entry point available.

## Current scope

New daily-report features and production scheduling belong to `quant-intel-platform` and `quant-intel-deploy`. This repository accepts maintenance needed to preserve legacy rendering, historical access, or a tested rollback path.
