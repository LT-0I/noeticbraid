# Dependency license notes

Runtime dependencies:

| Dependency | Purpose | License note |
| --- | --- | --- |
| Python 3.11+ standard library | JSON/JSONL, pathlib, datetime, tempfile, hashing | Python runtime is user environment; no bundled third-party code. |
| pydantic >=2,<3 | Runtime validation and serialization models | MIT; allowed by HBA whitelist. |

Test dependencies:

| Dependency | Purpose | License note |
| --- | --- | --- |
| pytest >=8 | Automated tests | MIT; allowed by HBA whitelist. |

Build backend:

| Dependency | Purpose | License note |
| --- | --- | --- |
| setuptools >=68 | Local package build metadata | MIT; allowed by HBA whitelist. |

Forbidden dependencies remain excluded: `pywin32`, `mcp-server-sqlite`, `portalocker`, GPL/LGPL/MPL/EPL/AGPL/PSF-2.0 third-party packages.
