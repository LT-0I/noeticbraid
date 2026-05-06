# noeticbraid-runtime

NoeticBraid SP-C2 module: Browser & CLI Runtime.

> NoeticBraid main repo: https://github.com/LT-0I/noeticbraid (Apache-2.0, public)

## Status

Implemented as standalone package `noeticbraid_runtime`:

- `BrowserSession` protocol for upper SP modules.
- `CdpSession` implementation with `navigate/eval/click/type_text/screenshot` per-call timeouts and a synchronous `close`.
- `launch_browser()` / `BrowserProcess` Playwright launcher wrapper with profile dir, CDP port, headless/headful mode, proxy args, and injectable launcher for tests.
- `get_session()` with explicit semantics: attach to `tab_id`, or attach first page / create `about:blank` when `tab_id=None`.
- `SelectorStore` hot-reloadable `selectors.json` loader.
- `CLISandbox` with command allowlist, cwd root guard, isolated environment overlay, and timeout-kill semantics.
- `_proxy.py` helpers for `HELIXMIND_TRUST_FAKE_IP_RANGE=198.18.0.0/15` Chrome bypass conversion.
- RunRecord-compatible artifact reference helpers that do not add frozen enum values.

## Boundaries

SP-C2 provides runtime primitives only. It does **not** manage account pools, run business automation, write vault files, schedule tasks, decrypt cookies, or implement DPAPI.

- Account pool and quota state belong to SP-C1.
- NotebookLM workflows belong to SP-H.
- Multi-model dispatch belong to SP-B.
- Vault/Obsidian writes belong to SP-D.
- Scheduling belongs to SP-E.

## Quick start

```powershell
cd C:\Users\13080\Desktop\HBA\noeticbraid\packages\noeticbraid-runtime
$env:PYTHONPATH='src'
python -m pytest -q
```

## Public API

```python
from noeticbraid_runtime import launch_browser, get_session
from noeticbraid_runtime.browser.session import BrowserSession
from noeticbraid_runtime.cli.sandbox import CLISandbox
```

### CLI sandbox

```python
from pathlib import Path
from noeticbraid_runtime.cli.sandbox import CLISandbox

sandbox = CLISandbox(allowed_commands=["python.exe"], allowed_roots=[Path.cwd()])
stdout, stderr, code = sandbox.run(["python", "-c", "print('ok')"], cwd=str(Path.cwd()))
```

### Browser launch

```python
from noeticbraid_runtime import launch_browser, get_session

process = launch_browser("runtime/chrome-profile", proxy_url=None, cdp_port=9222, headless=False)
session = get_session(cdp_port=9222)
session.navigate("https://example.com")
```

Live browser use requires optional dependencies:

```text
pip install -e .[browser]
playwright install chromium
```

Tests do not require Playwright, websocket-client, live Chrome, private profiles, cookies, or login.

## Docs

- `docs/IMPLEMENTATION_NOTES.md` - module layout and data flow.
- `docs/SECURITY_AND_COMPLIANCE.md` - runtime boundaries and forbidden behavior.
- `docs/DEPENDENCY_LICENSES.md` - dependency/license notes.
- `docs/MANUAL_BROWSER_SMOKE.md` - optional live Chrome smoke test steps.

## License

Apache-2.0
