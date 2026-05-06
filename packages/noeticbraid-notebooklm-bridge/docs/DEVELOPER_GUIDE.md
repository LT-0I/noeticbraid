# Developer Guide

## 1. Local environment

Use Python 3.11+ when possible. Install the package in editable mode from this repository root:

```powershell
python -m pip install -e .[dev]
```

The package has no runtime dependencies. The `dev` extra installs test-only tools.

## 2. Code style

There is no mandatory linter in this feature package. Keep implementation standard-library only, typed, small, and module-scoped. Put typed exceptions in `_errors.py`, public exports in `__init__.py`, small dataclasses in `_types.py`, selector handling in `_selectors.py`, contract serialization in `_serializer.py`, RunRecord event mapping/redaction in `_runlog.py`, and browser/UI operation flow in `_browser_ops.py`.

## 3. Running tests

Run all automated tests without NotebookLM or Google access:

```powershell
python -m pytest tests/ -q
python -m compileall noeticbraid
```

Contract-alignment tests need the main NoeticBraid OpenAPI file. If this repo is copied outside the HBA layout, set:

```powershell
$env:NOETICBRAID_CONTRACT_PATH='C:\path\to\phase1_2_openapi.yaml'
```

## 4. Fake sessions

`tests/conftest.py:FakeC2Session` simulates the current SP-C2 BrowserSession protocol:

- `navigate(url, timeout_s=...)`
- `eval(expression, await_promise=True, timeout_s=...)`
- `click(x, y, timeout_s=...)`
- `type_text(text, timeout_s=...)`

Do not add fake methods named `evaluate`, `wait_for`, `click(selector)`, or `type_text(selector, text)`; those hide C2-boundary regressions.

## 5. Package layout and selector hot reload

`selectors.json` uses the scoped `notebooklm` mapping consumed by `_selectors.SelectorStore`. Public browser operations call `_load_selectors()`, which supports hot-reload by environment variable:

```powershell
$env:NOETICBRAID_NOTEBOOKLM_SELECTORS='C:\path\to\custom_selectors.json'
```

Custom selector files must include all required semantic keys. Keep selector edits outside business logic so future SP-C2 selector management can provide the same scope/key data.
