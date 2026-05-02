# Phase 1.2 Stage 2 Integration Review Template

Candidate stage: Phase 1.2 Stage 2.4 integration contract CI archive seal
Frozen contract: `docs/contracts/phase1_2_openapi.yaml` (`info.x-contract-version: 1.1.0`)
Required local review outputs:

- `docs/reviews/phase1.2/stage2_integration_claude.md`
- `docs/reviews/phase1.2/stage2_integration_codex.md`
- `docs/reviews/phase1.2/stage2_integration_verdict.md`

Do not write final verdict text into this template. The local dual reviewers and arbitrator must create the three files above after applying the Stage 2.4 patch and running local verification.

## Reviewer identity

- Reviewer:
- Model / tool:
- Date:
- Candidate commit:
- Verdict: `PROCEED` / `CONCERN` / `BLOCK`

## Checklist

### 1. Seven-endpoint integration smoke

- [ ] `packages/noeticbraid-backend/tests/test_stage2_4_integration_smoke.py` creates exactly one `create_app(Settings(...))` instance for the smoke scenario.
- [ ] The smoke uses `httpx.ASGITransport` / `httpx.AsyncClient`; no browser automation, real network server, or new async pytest plugin is introduced.
- [ ] The one client calls all seven frozen paths: health, startup-token, dashboard, workspace, approval queue, account pool, and run ledger.
- [ ] `POST /api/auth/startup_token` is called without a request body.
- [ ] `GET /api/account/pool` uses a test-generated bearer and remains unauthorized without one in the existing regression suite.
- [ ] The seeded `RunRecord` is present in `/api/ledger/runs` and validates as a nested `RunRecord`.
- [ ] The seeded `ApprovalRequest` is present in `/api/approval/queue` and validates as a nested `ApprovalRequest`.
- [ ] All seven response wrappers validate against their frozen Pydantic models and preserve top-level field order.
- [ ] Public response bodies contain no private marker material.

### 2. Frozen YAML and sidecar byte gate

- [ ] `scripts/check_phase1_2_contract_gate.py` mechanically reads `docs/contracts/phase1_2_openapi.yaml` as bytes.
- [ ] The gate mechanically reads and parses `docs/contracts/phase1_2_openapi.yaml.sha256` as `<SHA256> *phase1_2_openapi.yaml`.
- [ ] The computed byte SHA-256 matches the sidecar digest.
- [ ] The frozen YAML still has exactly seven paths, expected operationIds, expected response refs, expected wrapper field order, and no startup-token request body.
- [ ] No OpenAPI YAML or sidecar edit is present in the patch.

### 3. Runtime OpenAPI and response drift

- [ ] Runtime OpenAPI from `create_app(Settings(...)).openapi()` has title `NoeticBraid Phase 1.2 API`, version `1.1.0`, `x-contract-version: 1.1.0`, `x-status: AUTHORITATIVE`, and `x-frozen: true`.
- [ ] Runtime paths, methods, tags, summaries, operationIds, and response schema refs match the frozen anchors.
- [ ] Runtime components contain exactly the 13 expected schema names.
- [ ] Runtime OpenAPI has no bearer security scheme, route-level security entry, or visible `Authorization` parameter.

### 4. Full tracked-repository private-leak scan

- [ ] `scripts/private_leak_scan.py` enumerates files via `git ls-files -z` and fails closed if that command is unavailable or not null-delimited.
- [ ] The scanner skips `private/**`, binary files, dependency directories, build outputs, and caches.
- [ ] The scanner reports only path, line number, and marker name with a redacted excerpt.
- [ ] Allowlist entries are narrow, documented, and limited to scanner/test lexicon use, internal backend auth implementation, sanitizer assertions, and contextual historical review text.
- [ ] `tests/test_private_leak_scan.py` covers null-delimited parsing, fail-closed behavior, private-path skipping, redaction, and contextual markdown assertions.

### 5. CI workflow closure

- [ ] `.github/workflows/ci.yml` installs the existing core and backend editable packages without adding dependencies.
- [ ] CI runs core pytest, backend pytest, root pytest gates, `scripts/contract_diff.py`, `scripts/check_source_of_truth_consistency.py`, the Phase 1.2 contract gate, the private-leak scan, and the sidecar byte integrity gate.
- [ ] The stale root `manifest.md` `contract_version: 1.0.0` grep gate is replaced by a Python sidecar integrity gate for `phase1_2_openapi.yaml`.

### 6. Frozen implementation and dependency boundaries

- [ ] No Stage 2.1 ledger implementation source was modified.
- [ ] No Stage 2.2 guard/auth/approval/account implementation source was modified.
- [ ] No Stage 2.3 Console read implementation source was modified.
- [ ] No frontend, Console swap, browser automation, SDK generation, or Lane C work is included.
- [ ] No new dependency is introduced.
- [ ] No private files, credential files, generated dependency artifacts, caches, or git metadata are included.

### 7. Audit-trail row readiness

- [ ] Local verifier has final Stage 2.4 integration commit evidence.
- [ ] Local verifier has final tag evidence.
- [ ] Local verifier has final Claude and Codex review artifacts under `docs/reviews/phase1.2/`.
- [ ] Local verifier has final verdict evidence with pytest, contract-gate, smoke, and private-leak scan outcomes.
- [ ] The final `docs/audit_trail.md` change is append-only, adds exactly one Phase 1.2 Stage 2 integration row, matches the existing table column count and style, and includes row diff evidence.

### 8. Stage 2.4 archive package completeness

The final archive must live under `GPT5_Workflow/archive/phase-1.2/stage-2.4/` and explicitly include:

- [ ] Stage 2.4 `prompt.md`.
- [ ] ContextBundle zip and bundle summary.
- [ ] GPT-A response summary, chat URL, response zip, and extracted response files.
- [ ] Prompt review artifacts.
- [ ] Implementation reply review artifacts.
- [ ] Arbitration files.
- [ ] Final NoeticBraid review artifacts: Claude review, Codex review, and verdict.
- [ ] Integration smoke output.
- [ ] Contract gate output.
- [ ] Private-leak scan output.
- [ ] Pytest logs.
- [ ] Final integration report.
- [ ] Final integration commit/tag evidence.
- [ ] Audit-trail append evidence.
- [ ] Archive `README.md`.
