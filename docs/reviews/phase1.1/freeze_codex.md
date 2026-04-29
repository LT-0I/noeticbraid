# Stage 1.5 (B Freeze) — Codex GPT-5.5 xhigh Review Summary

> Summary of the Stage 1.5 dual-review process; raw transcript at
> `GPT5_Workflow/.tmp/freeze_review_codex.md`.

## Verdict

**PARTIAL — 0D / 1S / 1M / 2L.** Substance of the freeze is correct, but CI
will fail at the install step due to a Stage 0/1 legacy PEP 440 violation.

## Findings

### S — PEP 440 invalid version (CI blocker)

`packages/noeticbraid-core/pyproject.toml:3` — `version = "0.1.0-stage0"` is
not valid PEP 440. CI step `pip install -e "packages/noeticbraid-core[test]"`
fails before pytest can even run.

This is a Stage 0/1 inheritance, not introduced by GPT-A. The freeze prompt
correctly forbade GPT-A from touching `pyproject.toml`. So GPT-A could not
fix it.

**Empirical reproduction (local main session)**: Python 3.11 + pip 26.1 +
latest hatchling produces `ValueError: Invalid version '0.1.0-stage0'`. CI
on Python 3.12 with the same toolchain would fail identically.

**Resolution**: local PR patch on the freeze branch changes `version` to
`"0.1.0+stage0"` (PEP 440 local-version segment, semantically equivalent —
preserves the "stage0" tag while satisfying PEP 440). Verified `pip install
-e` then succeeds; pytest then runs to 262 PASSED.

### M — OpenAPI HealthResponse stale example

`docs/contracts/phase1_1_openapi.yaml:90,93` — HealthResponse example values
remain `contract_version: 0.1.0` and `authoritative: false`, contradicting the
frozen reality (`1.0.0` / `true`). Misleads Stage 2 consumers.

**Resolution**: local PR patch updates both examples to `1.0.0` and `true`.

### L — `contract_diff.py` Optional / Union normalization

`scripts/contract_diff.py` uses `repr(annotation)` equality to compare bare
types. If one side defines a field as `Optional[X]` and the other as `X | None`,
repr would differ even though semantically equivalent. In the current artifact
both sides happen to use the same form, so `contract_diff` PASSes 6/6. But this
is a forward-looking fragility — Stage 2 schema authors might use different
syntax, breaking the gate spuriously. Future-improvement candidate (not blocker).

### L — PR / merge SHA placeholders

GPT-A correctly used `#TBD` / `TBD` everywhere (PR not yet created at freeze
time). Acceptable.

## 14-item compliance + 7 hidden risks

12/14 PASS, 1 PARTIAL (CI install step, due to S above), 1 PARTIAL (HealthResponse
M above). 7 hidden-risk checks all PASS.

## Verdict for merge

**PARTIAL → after S/M local patches → effectively PASS.** Does not require GPT-A
v2 freeze (S is on GPT-A's blacklist; cannot be fixed by GPT-A without scope
expansion).

## Disagreement with first review

Claude Opus first review: PASS 0D 0S (rated PEP 440 as L). Disagreement
**resolved**: the local main session reproduced PEP 440 failure on Python 3.11
+ latest hatchling, confirming Codex's S verdict. Final convergent verdict:
**PARTIAL → patch S/M locally → PASS for merge.**
