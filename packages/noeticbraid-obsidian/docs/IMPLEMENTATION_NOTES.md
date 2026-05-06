# SP-D implementation notes

## Design

SP-D is a local-file package, not an Obsidian plugin. It writes only under the configured namespace and defaults to `dry_run`; callers must explicitly choose live mode before any filesystem write.

The distribution package name is `noeticbraid-obsidian`; the import package is `noeticbraid_obsidian`.

## Components

- `__init__.py`: curated public imports for the current package surface.
- `dashboard.py`: generated dashboard bodies, weekly dashboard support, and `## Manual notes` preservation.
- `errors.py`: typed package exceptions (`ObsidianHubError`, `SettingsError`, `PathPolicyError`, `RenderError`, `WritePolicyViolation`).
- `frontmatter.py`: minimal YAML frontmatter subset used for portable Markdown notes.
- `inbox_watcher.py`: polling dropzone scanner for user-authored Markdown task requests; emits stable `source_obsidian_<hash>` refs and keeps the vault path in a vault-only field.
- `path_policy.py`: allowlist, denylist, traversal rejection, and deterministic object-to-path resolution.
- `renderer.py`: transforms backend/vault objects into contract `1.3.0` frontmatter and Markdown body, with enum validation loaded from embedded schemas.
- `resources.py`: resource loaders for embedded schemas, settings, fixtures, and templates.
- `settings.py`: fail-closed write-policy settings loaded from the embedded JSON example.
- `validate_obsidian_hub.py`: resource/schema/settings/path-policy/template-instance self-check.
- `writer.py`: same-directory atomic writes, create-only stable records, generated dashboard overwrite with manual-note preservation, heading-limited appends, and sync-log append.
- `config/obsidian_hub.settings.example.json`: serialized dry-run default write policy.
- `fixtures/path_policy_cases.json`: positive/negative path-policy cases.
- `schemas/*.schema.json`: embedded Obsidian Hub contract `1.3.0` note/settings schemas.
- `templates/*.md`: schema-backed note templates for dashboard/task/run/source/side-note/digestion plus project helper template.

## API surface decision

See `docs/API_DECISION.md`. The BLUEPRINT now follows the implemented `RenderedNote`-centric writer/renderer API and the `InboxWatcher.scan_once(...)` polling API. `watch()` remains deferred rather than introducing watchdog or plugin dependencies.

## Sync log append-only exception

`VaultWriter.record_sync_log()` intentionally bypasses full-file atomic replacement. The sync log is an append-only audit surface: each line is written, flushed, and fsynced before returning, so the write intent is line-oriented instead of whole-document atomic. Readers must treat trailing partial lines as recoverable/incomplete records.

This exception is limited to the configured sync log path and does not weaken generated dashboard or stable-record write policy.

## Open-source reference impact

- Local REST API projects show useful future REST/heading/frontmatter patch semantics, but this package remains local-file only.
- TaskNotes demonstrates the portability benefit of storing tasks as Markdown notes with YAML frontmatter.
- Dataview demonstrates why generated notes should expose stable frontmatter fields rather than plugin-private databases or arbitrary JavaScript.

## Backlog (deferred to 1.3.x)

- Obsidian plugin implementation.
- Local REST API / CLI REST bridge.
- Watchdog-based live filesystem watching.
- Obsidian Git/LiveSync orchestration.
- Assess whether `dashboard.py` should self-inject `generated_at` for generated bodies; current behavior keeps timestamp injection in `MarkdownRenderer.render_dashboard(...)` so callers control clock/source-run provenance.
- Revisit top-level exports for base exceptions (`ObsidianHubError`, `SettingsError`, `RenderError`) after public API stabilization; currently they are available from `noeticbraid_obsidian.errors`.
