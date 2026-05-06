# Security and compliance

## Allowed behavior

- Store local account aliases and non-secret provider/capability labels.
- Store local quota estimates, cooldown windows, and sanitized status labels.
- Hash raw observed text instead of persisting it.
- Emit sanitized `profiles[]` summaries for the frozen account-pool wrapper.

## Forbidden behavior

- No cookies, browser profile reads, token export, OAuth rotation, or credential scraping.
- No browser or CLI runtime launchers in SP-C1.
- No DPAPI implementation in this package.
- No `tokens.sqlite` generation.
- No `pywin32`, `mcp-server-sqlite`, or `portalocker`.
- No GPL/LGPL/MPL/EPL/AGPL/PSF-2.0 third-party dependencies.
- No frozen NoeticBraid contract modification.

## Redaction

`sanitize_reason()` removes assignment-style secret values and common secret words before event serialization. `SessionHealthRecord.observed_text` is excluded from serialization, while `observed_text_hash` stores a SHA-256 digest for correlation.
