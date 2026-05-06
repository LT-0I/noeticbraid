# Selector Maintenance

`selectors.json` uses a scoped shape compatible with the C2 selector-store style:

```json
{
  "notebooklm": {
    "add_source_button": ["button[aria-label*='Add source' i]", "text=Add source"]
  }
}
```

Keep semantic keys stable. Update only candidate selectors after manually inspecting NotebookLM in a user-authorized browser. Prefer accessible labels and visible text fallbacks. Do not add selectors that target credentials, cookies, hidden auth state, or account internals.

When a selector fails, SP-H raises a typed timeout or selector error. Fix the selector config and rerun the fake-session tests plus a manual NotebookLM smoke test.
