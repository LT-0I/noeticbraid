# SP-D API decision: implementation-aligned surface

Date: 2026-05-06
Decision: **A / update BLUEPRINT to match implementation**.

## Decision

The canonical SP-D public surface for this package is the implemented `RenderedNote`-centric API:

- `MarkdownRenderer.render_*` methods return `RenderedNote(frontmatter, body)` rather than a raw `(frontmatter, body)` tuple.
- `VaultWriter.write_dashboard(dashboard_id, note)` and `write_stable_record(..., note, date=..., project=...)` consume `RenderedNote` so writer policy checks see the exact serialized frontmatter.
- `VaultWriter.append_to_heading(relative_path, heading, content)` targets a policy-checked relative vault path, not a record id.
- `InboxWatcher.scan_once(...)` is the supported intake API for this phase; long-running `watch()` is deferred to avoid watchdog/runtime dependencies.
- `DashboardGenerator.generate_this_week(...)` is implemented alongside today/digestion/account-pool helpers.

## Rationale

This keeps rendering, policy validation, and filesystem writing separated while still preserving a precise markdown artifact boundary. It also keeps SP-D dependency-free and local-file-only for the current module package.

## Non-goals retained

- No Obsidian plugin implementation.
- No Local REST API bridge.
- No browser launch, OAuth/cookie/profile handling, DPAPI wrapper, SQLite token store, or network write path.
- No mutation of NoeticBraid frozen contracts.
