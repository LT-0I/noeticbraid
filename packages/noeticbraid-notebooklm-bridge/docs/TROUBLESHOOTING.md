# Troubleshooting

## Login required

`NotebookLMLoginRequiredError` means Google or NotebookLM is asking for login, MFA, CAPTCHA, account selection, or terms confirmation. Complete the step manually in the SP-C2 browser session and retry.

## Selector timeout

NotebookLM UI changed or the target is not visible. Inspect the page manually and update `selectors.json` candidates under the stable semantic key.

## Session contract error

The supplied object must provide `navigate`, `eval`, `click(x, y)`, and `type_text(text)`. If using a higher-level adapter, ensure it preserves this current C2 shape.

## Empty Briefing Doc

Confirm sources are ready and NotebookLM has generated the Briefing Doc. Increase `timeout_s` for slow generation.

## Contract validation failure

Do not edit frozen contracts. Update serializer mapping to fit the existing `SourceRecord` / `RunRecord` schemas.
