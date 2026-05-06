# Architecture

`notebooklm_bridge` is a narrow SP-H library. It sits above SP-C2 Browser Runtime and below SP-B Multimodel Alliance. SP-A Radar and SP-G Evolution provide source items; SP-H adds them to NotebookLM and returns generated artifacts and strict contract records.

## Modules

- `__init__.py`: stable public API and exported errors.
- `_protocols.py`: current SP-C2-compatible `BrowserSession` protocol.
- `_selectors.py`: scoped selector loader compatible with C2 selector-store shape.
- `_browser_ops.py`: NotebookLM UI operation flow.
- `_serializer.py`: strict `SourceRecord 1.0.0` serializer.
- `_runlog.py`: strict `RunRecord 1.0.0` event adapter.
- `_errors.py`: typed exception hierarchy.
- `_types.py`: small dataclasses.

## Data flow

1. Validate public inputs.
2. Navigate to `https://notebooklm.google.com/notebook/<notebook_id>`.
3. Detect login/MFA/CAPTCHA/terms gates and stop for manual action.
4. Resolve semantic selectors to DOM coordinates through `session.eval`.
5. Click via C2 `click(x, y)` and enter text via `type_text(text)`.
6. Extract visible generated text through `session.eval`.
7. Serialize outputs to strict contract dictionaries and emit strict RunRecord-compatible events.

## Browser boundary

SP-H never starts or closes Chrome, opens CDP sockets, reads cookies, stores profiles, or installs Playwright/Patchright. SP-C2 supplies the user-authorized session.

## Contract boundary

The serializer uses only frozen SourceRecord properties. The event adapter uses existing RunRecord event enums and string `artifact_...` references. Frozen OpenAPI files are never edited.
