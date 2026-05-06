# Security and Compliance

This package is only for authorized, user-controlled NotebookLM browser automation.

SP-H must not bypass login, MFA, CAPTCHA, account gates, paywalls, terms prompts, quotas, rate limits, or access controls. It must not read, decrypt, export, or persist cookies, passwords, browser profiles, or credential stores. It must not include stealth, fingerprint spoofing, CAPTCHA solving, or anti-detection logic.

Runtime dependencies are standard-library only. Forbidden dependencies include `pywin32`, `mcp-server-sqlite`, Playwright/Patchright/Selenium inside SP-H, GPL/LGPL/MPL/EPL/AGPL/proprietary/unknown-license packages, and any credential extraction or evasion tool.

Generated data is returned to callers and not persisted by SP-H. Logs and events are redacted.
