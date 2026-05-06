# Security and compliance

## Allowed

- Render sanitized contract `1.3.0` frontmatter and Markdown bodies.
- Write generated dashboards and stable records under allowlisted `NoeticBraid/` roots.
- Read only the explicit `NoeticBraid/80_inbox/user_dropzone/` dropzone for task intake.
- Append non-secret sync-log events.

## Forbidden

- No credential, cookie, OAuth token, DPAPI blob, browser profile, or private path storage.
- No `20_episodic_memory/10_user_raw/` writes or reads.
- No browser/Obsidian launchers.
- No Local REST API calls in this phase.
- No SQLite, `pywin32`, `mcp-server-sqlite`, or `portalocker`.
- No GPL/LGPL/MPL/EPL/AGPL/PSF-2.0 dependencies.
- No frozen contract modification.

## Dependency stance

Runtime is stdlib-only. Test extra uses `pytest` only.
