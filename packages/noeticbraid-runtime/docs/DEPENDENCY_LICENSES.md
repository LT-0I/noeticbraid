# Dependency license notes

Runtime core dependencies:

| Dependency | Purpose | License note |
| --- | --- | --- |
| Python 3.11+ standard library | subprocess, pathlib, urllib, JSON, base64, dataclasses | User environment; no bundled third-party code. |

Optional browser dependencies:

| Dependency | Purpose | License note |
| --- | --- | --- |
| playwright >= 1.44 | Live Chrome persistent-context launch | Apache-2.0; allowed. |
| websocket-client >= 1.6 | Live CDP websocket transport | Apache-2.0; allowed. |

Test dependencies:

| Dependency | Purpose | License note |
| --- | --- | --- |
| pytest >= 8 | Automated tests | MIT; allowed. |

Forbidden dependencies remain excluded: `pywin32`, `mcp-server-sqlite`, `portalocker`, GPL/LGPL/MPL/EPL/AGPL packages.
