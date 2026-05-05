# NoeticBraid Audit Trail

Append-only record of all phase milestones with dual review evidence.

Each row links the merge commit / tag to the dual review summaries (Claude Opus
1M MAX + Codex GPT-5.5 xhigh). New rows append to the bottom; rows are never
edited or removed.

| Phase | Stage | PR | Merge SHA | Tag | Claude Review | Codex Review | Verdict |
|---|---|---|---|---|---|---|---|
| 1.1 | Stage 1 import | - | b8d7152 | phase-1.1-stage1-candidate | docs/reviews/phase1.1/stage1_claude.md | docs/reviews/phase1.1/stage1_codex.md | PASS |
| 1.1 | Freeze | #1 | 4be314d | phase-1.1-contract-1.0.0 | docs/reviews/phase1.1/freeze_claude.md | docs/reviews/phase1.1/freeze_codex.md | PASS (Codex S/M patched locally) |
| 1.1 | Stage 2 ledger | #3 | ba8166b | - | docs/reviews/phase1.1/stage2_ledger_claude.md | docs/reviews/phase1.1/stage2_ledger_codex.md | PASS (consensus 2M deferred to Phase 1.2: reader LOCK_SH + iter_all generator handle) |
| 1.1 | Stage 2 guard | #4 | bcfa1a1 | - | docs/reviews/phase1.1/stage2_guard_claude.md | docs/reviews/phase1.1/stage2_guard_codex.md | PASS |
| 1.1 | Stage 2 console | #5 | bcc5502 | - | docs/reviews/phase1.1/stage2_console_claude.md + stage2_console_patch_claude.md | docs/reviews/phase1.1/stage2_console_codex.md + stage2_console_patch_codex.md | PASS (local patched 1 vitest race + 1 src/README; package.json description NOT modified per v3 byte-freeze) |
| 1.1 | Stage 2 integration | #6 | 510350a | phase-1.1-complete | (rolled-up review evidence above) | (rolled-up review evidence above) | PASS (CI gate green: pytest 383 / contract_diff / source_of_truth / private leak / vitest 6/6 / typecheck) |
| 1.2 | Stage 1 backend skeleton | - | 5650751 | phase-1.2-stage1-candidate | docs/reviews/phase1.2/stage1_v1_claude.md + stage1_v2_claude.md | docs/reviews/phase1.2/stage1_v1_codex.md + stage1_v2_codex.md | PROCEED (v1 REVISE_GPT_A → v2 PROCEED, 15 pytest pass, OpenAPI 13 schemas verified) |
| 1.2 | Stage 1.5 contract freeze (2026-05-01, contract 1.1.0) | - | - | phase-1.2-contract-1.1.0 | GPT5_Workflow archive/phase-1.2/stage-1.5/phase1.2_stage1.5/reviews/reviewer_A.md (CONCERN, claudecode sonnet 4.6) | GPT5_Workflow archive/phase-1.2/stage-1.5/phase1.2_stage1.5/reviews/reviewer_B.md (CONCERN, codex) | PROCEED after local fixes: sha256 0667BDEC52CB4FE958D526BD171D43B21ECF92A2B2B56EEF53C11BB0CB818438; fix1 title updated to Phase 1.2; fix2 source OpenAPI snapshot wrapper order verified alphabetical, no schema reorder; fix3 GPT-A response self-check body unavailable in archive, review_template.md preserves equivalent checklist |
| 1.2 | Stage 2.1 ledger storage backend | - | e5d4ad0 | phase-1.2-stage-2.1-candidate | GPT5_Workflow archive/phase-1.2/stage-2.1/reviews/ (Reviewer A claudecode sonnet 4.6, PROCEED 5 MINOR) | GPT5_Workflow archive/phase-1.2/stage-2.1/reviews/reply_reviewer_B.md (CONCERN, codex) | PROCEED with integration-time fixes: real pytest run (core 386 / backend 20 PASS), manifest decision_log + open_questions sections added, run_ledger.py pragma removed |
| 1.2 | Stage 2.2 guard auth approval backend | - | 9f276c7 | phase-1.2-stage-2.2-candidate | GPT5_Workflow archive/phase-1.2/stage-2.2/reviews/reply_reviewer_A.md (PROCEED 3 MINOR, claudecode sonnet 4.6) | GPT5_Workflow archive/phase-1.2/stage-2.2/reviews/reply_reviewer_B.md (CONCERN 2 MAJOR + 2 MINOR, codex) | PROCEED with 5 integration-time fixes (vault env single-source, OSError fail-closed, DPAPI use_last_error, guard __all__ ordering, CORS expose_headers deferred); pytest core 398 / backend 42 PASS |
| 1.2 | Stage 2.3 console read API backend | - | 7f88f2a | phase-1.2-stage-2.3-candidate | GPT5_Workflow archive/phase-1.2/stage-2.3/reviews/reply_reviewer_A.md (APPROVE/PROCEED 1 MED + 2 LOW, claudecode sonnet 4.6) | GPT5_Workflow archive/phase-1.2/stage-2.3/reviews/reply_reviewer_B.md (CONCERN 1 MAJOR + 2 MINOR + 1 INFO, codex) | PROCEED with 3 integration-time fix groups (dashboard sanitizer markers + strict diff_ref allowlist, full 40-character GitHub citation SHAs, SHA sidecar file comparison); pytest core 398 / backend 52 PASS |
| 1.2 | Stage 2 integration seal | - | 32f3882 | phase-1.2-stage-2-complete | GPT5_Workflow active/phase1.2_stage2/stage-2.4/reviews/reply_reviewer_A.md (APPROVE/PROCEED 1 MED + 2 LOW, claudecode sonnet 4.6) | GPT5_Workflow active/phase1.2_stage2/stage-2.4/reviews/reply_reviewer_B.md (CONCERN 1 MAJOR + 1 MINOR + 2 INFO, codex) | PROCEED with 4 integration-time fixes (Phase 1.1 freeze grep restored, leak scan allowlist narrowed, account_hint comment added, duplicate inline sidecar Python removed); evidence GPT5_Workflow active/phase1.2_stage2/stage-2.4/T053_integration_report.md + T053_pytest_core.txt + T053_pytest_backend.txt + T053_smoke.txt + T053_contract_gate.txt + T053_leak_scan.txt |
| 1.2 | Module account/quota extension | - | e45c169 | module-account-quota-v0 | GPT5_Workflow archive/modules/module-account-quota/reviews/reviewer_A.md (APPROVE 1 MED + 2 LOW, claudecode sonnet 4.6) | GPT5_Workflow archive/modules/module-account-quota/reviews/reply_reviewer_B.md (CONDITIONAL PASS 1 MAJOR + 3 MINOR, codex) | PROCEED with integration-time fix B-1 (MalformedAccountQuotaState from None + exception-chain regression); pytest core 398 / backend 72 PASS; evidence GPT5_Workflow archive/modules/module-account-quota/reply_arbitrate.md + integration_report.md |
| 1.2 | Module user-growth LLMwiki extension | - | 41aecb3 | module-user-growth-llmwiki-v0 | GPT5_Workflow archive/modules/module-user-growth-llmwiki/reply_arbitrate.md (A summary: COMMENT 2 MED + 2 LOW) | GPT5_Workflow archive/modules/module-user-growth-llmwiki/reviews/reply_reviewer_B.md (REQUEST CHANGES 2 HIGH + 2 MED, codex) | PROCEED with 4 integration-time fixes (fixture-only scanner boundary + RealVaultIntegrationBoundary, SQLite INSERT duplicate failure, SourceRecord raw/source-only validator, VaultProfile source-record materialization); pytest core 408 PASS; evidence GPT5_Workflow archive/modules/module-user-growth-llmwiki/integration_report.md |

## T-MID-1 contract-1.2.0 integrate (2026-05-03)

- step 7 integration: applied 11 yaml fixes (F-Y1~F-Y11 from active/contract-1.2.0/step6_arbitrate.md section 3.1) + 2 vault_layout fixes (F-V1~F-V2)
- new contract surface: 4 schemas (Workflow, ModelRoute, VaultLayoutMinimum, RunRecordAggregate) + 1 endpoint (GET /api/ledger/runs/aggregate) + 1 sidecar (vault_layout.yaml) + 1 fixture copy (path_policy_cases.json)
- frozen baseline preserved: 13 schemas + 7 paths byte-equal vs 1.1.0
- new sha256: phase1_2_openapi.yaml = 96CE4BAC5E3C9F1C976E21BC68D32FF2BA02C5EF9FE16BB8189EB3FBFBF839B7
- gates: pytest core 414, backend 74, contract_gate PASS, leak_scan PASS, smoke PASS
- step 6 arbitrate verdict: PROCEED with integration-time fixes
- source response: T058 chat URL https://chatgpt.com/g/g-p-69f5d138952c8191830bffd0dad8d4d4-noeticbraid-v33/c/69f7211c-e0e0-8328-8b72-273ad826a333 (response.zip sha256 a0d19b5d56b2d1e36ed3063ade825f9c4cce6ffaef7d46e0c90a45c25664f29f)
- tag pending main session: phase-1.2-contract-1.2.0

## T-MID-2 contract-1.3.0 integrate (2026-05-05)

- step 7 integration commit 9965e1c9a7dfa4cdaddb92633d86a59b3d1ca1aa, tag phase-1.2-contract-1.3.0, pushed origin main + tag
- step 6 arbitrate verdict: PROCEED with integration-time fixes (P1 source_record_note evidence_role/used_for_purpose anyOf nullable + P2 source_ref vault-only standardized description)
- step 5 reply dual review: Reviewer A claudecode sonnet 4.6 CONCERN 0/0/3/2; Reviewer B codex CLI PASS 0/0/0/0
- new contract surface: 7 obsidian-hub schemas (dashboard, task_note, run_record_note, source_record_note, side_note, digestion_item, write_policy) under docs/contracts/obsidian-hub-1.3.0/ + phase1_3_openapi.yaml (pure-增量, paths:{}, 7 component refs)
- 7 pydantic models under packages/noeticbraid-core/src/noeticbraid_core/schemas/obsidian_hub/ with NO-LEAK comments on text/path/url fields
- 8 contract-1.3.0 pytest cases (test_obsidian_hub_1_3_0.py) + 2 frozen 1.2.0 byte-equal regression cases (test_frozen_1_2_0_byte_equal.py)
- frozen baseline preserved: phase1_2_openapi.yaml sha256 96CE4BAC5E3C9F1C976E21BC68D32FF2BA02C5EF9FE16BB8189EB3FBFBF839B7 + vault_layout.yaml CCB2D878A8200E13267DF0FDCDF25844084E4F517F711EC47858F8FBCF533D91 byte-equal
- new sha256: phase1_3_openapi.yaml = 26A3990C31382CCFACB299773AB922775A7907C735430DA7293B794208068274
- gates: license_check_gate 27 PASS / 3 FAIL covered by EXCEPTION-4 (pywin32 PSF transitive of portalocker, T073 fix planned) + EXCEPTION-5 (certifi MPL transitive of httpx, industry-accepted) + EXCEPTION-6 (typing_extensions PSF-2.0, Python core team backport); private_leak_scan PASS 221 scanned; phase1_2_contract_gate PASS sidecar=96CE4BAC...; pytest core 424 (was 414 in 1.2.0, +10 for 1.3.0); pytest backend 74
- license_check_gate.py upgraded to PEP 639 License-Expression + Classifier fallback + UTF-8 subprocess (24 false-positive empty fields collapsed to 3 real PSF/MPL violations covered by EXCEPTIONS)
- source response: GPT-A chat URL https://chatgpt.com/c/69f9dc41-3668-83e8-b1c5-b9f3653ce2bb (response.zip sha256 EA963020475BBDE3BD9E1034BD5705EB4D1A95EFEA60A2BD8F67AD1CA0275D63)
