# NoeticBraid SP-H NotebookLM Bridge

NoeticBraid SP-H is the NotebookLM Bridge feature package. It accepts vetted URL/text sources from upstream SP-A Radar or SP-G Evolution, drives a user-authorized NotebookLM notebook through an injected SP-C2 browser session, pulls generated Briefing Doc / FAQ outputs, and serializes generated output into strict `SourceRecord 1.0.0` dictionaries for downstream SP-B use.

This v2 implementation keeps the original `BLUEPRINT.md` and `REVIEW.md` in place and fixes the main gaps found in the first zip draft:

- strict frozen `SourceRecord 1.0.0` output, no extra fields;
- strict frozen `RunRecord 1.0.0`-compatible event payloads, no new enum values;
- current SP-C2 session boundary: `navigate`, `eval`, `click(x, y)`, `type_text(text)`;
- scoped selector config compatible with the C2 `SelectorStore` style;
- no browser lifecycle, auth, cookie, profile, Playwright, Patchright, MCP server, or undocumented Google RPC ownership inside SP-H.

## Public API

```python
from noeticbraid.tools.notebooklm_bridge import (
    push_sources,
    pull_briefing,
    pull_faq,
    to_source_records,
)

source_refs = push_sources(
    session,
    notebook_id="example_notebook_id",
    sources=[
        {"url": "https://example.com/paper"},
        {"title": "SP-G Reflection", "text": "Evidence text..."},
    ],
)

briefing = pull_briefing(session, "example_notebook_id")
faq = pull_faq(session, "example_notebook_id")
records = to_source_records("example_notebook_id", briefing, run_id="run_123")
```

## Install and test

```bash
python -m pip install -e .[dev]
python -m pytest -q
python -m compileall noeticbraid
```

Automated tests use a fake SP-C2 session. They do not require Google login or live NotebookLM access.

## Boundaries

SP-H does not bypass Google login, MFA, CAPTCHA, account gates, terms prompts, paywalls, quotas, rate limits, or access controls. If a gated state appears, SP-H raises `NotebookLMLoginRequiredError` and requires manual user/SP-C2 action.

SP-H also does not manage browser profiles, cookies, credentials, Chrome processes, CDP sockets, Playwright/Patchright runtimes, MCP transports, account quota, or SP-B decision logic.

## Documentation

- `docs/REFERENCE_RESEARCH.md` - what was absorbed/rejected from the reference projects.
- `docs/ARCHITECTURE.md` - components, data flow, and boundaries.
- `docs/API_REFERENCE.md` - public API and errors.`n- `docs/DEVELOPER_GUIDE.md` - local development, tests, fake sessions, and package layout.
- `docs/C2_BROWSERSESSION_CONTRACT.md` - current SP-C2 session expected by SP-H.
- `docs/SELECTOR_MAINTENANCE.md` - selector hot-update workflow.
- `docs/RUNRECORD_INTEGRATION.md` - RunRecord-compatible event mapping.
- `docs/SECURITY_AND_COMPLIANCE.md` - safety and license constraints.
- `docs/TROUBLESHOOTING.md` - common failures.
- `docs/ROADMAP.md` - future integration work.

## License

Apache-2.0. Reference projects influenced architecture only; no source code was copied.

