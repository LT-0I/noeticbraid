# Dependency License Gate

Allowed whitelist: Apache-2.0 / MIT / BSD-2-Clause / BSD-3-Clause / ISC.

Direct dependencies:

- `jsonschema>=4,<5` ? runtime, MIT.
- `pytest>=8,<9` ? test extra, MIT.
- `setuptools>=68` ? build backend, MIT.

Gate command run from HBA root:

```powershell
python C:\Users\13080\Desktop\HBA\GPT5_Workflow\.codex\scripts\license_check_gate.py --package jsonschema pytest setuptools
```

Result on 2026-05-06:

```text
Summary: 12 PASS, 0 FAIL
License gate: PASS
```

No pywin32, mcp-server-sqlite, portalocker, GPL/LGPL/MPL/EPL/AGPL dependency is introduced.
