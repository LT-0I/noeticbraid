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
