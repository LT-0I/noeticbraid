# SP-C2 implementation notes

## Package layout

Implemented package: `src/noeticbraid_runtime/`.

- `browser/session.py`: `BrowserSession` protocol consumed by upper SP modules.
- `browser/cdp_session.py`: CDP-backed session implementation. Live mode uses optional `websocket-client`; tests inject a fake transport.
- `browser/playwright_launcher.py`: Playwright persistent-context launcher wrapper and deterministic Chrome args.
- `browser/selector_store.py`: hot-reloadable selector JSON store.
- `cli/sandbox.py`: allowlisted subprocess wrapper with cwd root guard and timeout kill semantics.
- `_proxy.py`: proxy and HelixMind fake-IP bypass helpers.
- `run_record.py`: frozen RunRecord-compatible artifact reference helpers.

## Review CONCERN fixes

- Command allowlist: `CLISandbox` requires non-empty `allowed_commands` and matches executable basename/stem.
- CWD guard: every run resolves `cwd` and requires it to be inside one configured allowed root.
- Timeout kill semantics: subprocess timeout starts the child in a killable process group, terminates the process tree, then raises `CLISandboxTimeout`; stdout/stderr fragments are retained where available.
- BrowserSession timeout: `navigate/eval/click/type_text/screenshot` all accept `timeout_s`.
- `get_session` semantics: `tab_id=None` attaches to first page target, or creates `about:blank`; explicit tab ids must exist.

## Frozen contract boundary

C2 consumes frozen schemas only. It does not add OpenAPI fields or new RunRecord event types. Runtime information is carried through existing `artifact_refs[]` using `artifact_`-prefixed strings.

## C1 integration (deferred)

`get_session` is currently attach-only mode: with an explicit `tab_id`, it reconnects to an existing page target; with `tab_id=None`, it attaches to the first page target or creates an `about:blank` CDP target.

The complete blueprint semantics for creating a new session through C1 account/profile allocation must wait for SP-C1 integration. After C1 is available, add a separate path such as `from noeticbraid_runtime.c1_bridge import allocate_session_with_profile` rather than expanding frozen contract fields in C2.
