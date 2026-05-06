# noeticbraid-sp-D-obsidian

NoeticBraid SP-D module: local Obsidian vault hub for policy-checked Markdown rendering, generated dashboards, dropzone task intake, and atomic local vault writes.

> NoeticBraid main repo: https://github.com/LT-0I/noeticbraid (Apache-2.0, public)

## Status

Implemented as a standalone Python package: distribution `noeticbraid-obsidian`, import package `noeticbraid_obsidian`.

Included capabilities:

- embedded Obsidian Hub contract `1.3.0` JSON schemas
- write-policy settings with fail-closed `dry_run` default
- path allowlist/denylist/traversal enforcement
- Markdown frontmatter rendering for dashboard, task, run record, source record, side note, and digestion item notes
- generated dashboard body helpers with `## Manual notes` preservation
- `VaultWriter` with same-directory atomic write and create-only stable record protection
- append-only sync log
- polling `InboxWatcher` for `NoeticBraid/80_inbox/user_dropzone/*.md`
- module-local validator (`python -m noeticbraid_obsidian.validate_obsidian_hub`)

## Boundaries

SP-D is not an Obsidian plugin and does not call Obsidian Local REST APIs in this phase. It operates directly on Markdown files under an explicitly supplied local vault root, with `dry_run` as the default mode.

It does **not**:

- read `20_episodic_memory/10_user_raw/`
- launch browsers, CLIs, or Obsidian
- manage Obsidian Git/LiveSync
- store credentials, cookies, OAuth tokens, DPAPI blobs, or profile paths
- introduce `pywin32`, `mcp-server-sqlite`, `portalocker`, SQLite, GPL-family dependencies, or network write paths
- modify NoeticBraid frozen contracts

## Open-source references used

- `coddingtonbear/obsidian-local-rest-api`: validated the future direction for targeted note/heading/frontmatter operations while keeping this phase local-file only.
- `callumalpass/TaskNotes`: reinforced the "task as Markdown note with YAML frontmatter" design for portability.
- `blacksmithgu/Obsidian Dataview`: reinforced keeping notes readable/queryable through frontmatter and avoiding unsafe generated JavaScript.
- `dsebastien/obsidian-cli-rest`: reinforced localhost/API-key automation as a future optional bridge, not part of this package.

## Quick start

```powershell
cd C:\Users\13080\Desktop\HBA\sp-repos\noeticbraid-sp-D-obsidian
$env:PYTHONPATH='src'
python -m pytest -q
python -m noeticbraid_obsidian.validate_obsidian_hub
```

### Dry run

```python
from pathlib import Path
from noeticbraid_obsidian import MarkdownRenderer, VaultWriter, default_settings

renderer = MarkdownRenderer()
writer = VaultWriter(Path("example-vault-root"), default_settings())
note = renderer.render_dashboard(
    dashboard_id="today",
    title="Today",
    date="2026-05-06",
    generated_at="2026-05-06T12:00:00Z",
    body="## Today\n- Preview only",
)
result = writer.write_dashboard("today", note)
assert result.dry_run is True
```

### Live mode

`live` mode must be explicit:

```python
from noeticbraid_obsidian import default_settings

settings = default_settings(write_mode="live")
```

The serialized default settings resource remains `dry_run`.

## Package layout

```text
src/noeticbraid_obsidian/
  __init__.py
  dashboard.py
  errors.py
  frontmatter.py
  inbox_watcher.py
  path_policy.py
  renderer.py
  resources.py
  settings.py
  validate_obsidian_hub.py
  writer.py
  config/obsidian_hub.settings.example.json
  fixtures/path_policy_cases.json
  schemas/*.schema.json
  templates/dashboard_today.md
  templates/digestion_item.md
  templates/project.md
  templates/run_record.md
  templates/side_note.md
  templates/source_record.md
  templates/task.md
```

## License

Apache-2.0
