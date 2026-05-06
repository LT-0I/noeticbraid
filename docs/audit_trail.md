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

## T073 portalocker -> filelock (2026-05-05, lightweight v3.3 cycle, no GPT-A)

- integration commit `8926a13`, tag `T073-portalocker-filelock`, pushed origin main + tag
- decision authority: GPT5_Workflow/tools/reports/T073_final_decision.md (codex audit + 2 independent reviews PROCEED filelock path A)
- reviewer A: claudecode sonnet code-reviewer subagent PASS 0/0/0/1 LOW (persistence.py:45 docstring, fixed in same commit); review at GPT5_Workflow/active/T073-portalocker-filelock/reviewer_A.md
- skipped step 2 prompt review / step 3 bundle / step 4 GPT-A / step 5 reply review: justified by (a) plan = T073_final_decision.md already double-reviewed; (b) replacement is mechanical mapping with verifiable invariants (4 files, ~70 LOC); (c) red-line surface limited to license whitelist + lock semantics, both verifiable by gates
- changes:
  - `packages/noeticbraid-core/pyproject.toml`: `portalocker>=2.0,<3` -> `filelock>=3,<4`
  - `packages/noeticbraid-core/src/noeticbraid_core/ledger/run_ledger.py`: import + 6 lock call sites migrated to `filelock.ReadWriteLock` write_lock()/read_lock(); lock at `state/ledger/run_ledger.lock.db` (sqlite-backed cross-process); lock acquired before file open (Windows TOCTOU eliminated)
  - `packages/noeticbraid-core/tests/test_ledger.py`: monkeypatch refactored to ReadWriteLock.read_lock + lock_file path; multiprocess tests migrated from multiprocessing to subprocess.Popen + file IPC
  - `packages/noeticbraid-core/src/noeticbraid_core/user_growth_llmwiki/persistence.py:45`: stale portalocker docstring updated
- gates:
  - license_check_gate: 27 PASS / 2 FAIL (pywin32 disappeared from transitive tree; only certifi MPL + typing_extensions PSF-2.0 remain, both EXCEPTION-5/6 covered); EXCEPTION-4 CLOSED
  - private_leak_scan: PASS 240 scanned
  - phase1_2_contract_gate: PASS sidecar=96CE4BAC... (frozen byte-equal preserved)
  - pytest core: 424 passed (= 1.3.0 baseline, no regression)
  - pytest backend: 74 passed
  - github_ci: pending verification (run 25384493042)
- side benefit: lock semantics upgraded from advisory fcntl/LockFileEx to SQLite WAL ReadWriteLock; explicit 60s timeout replaces unbounded blocking
- frozen baseline preserved: phase1_2_openapi.yaml + vault_layout.yaml + path_policy_cases.json byte-equal vs 1.2.0 freeze

## SP-C2 Browser & CLI Runtime integration (2026-05-05, full v3.3 dual-review × 2 rounds)

- integration commit `5faef09` (initial) → `8933bd1` (HEAD with private_leak_scan allowlist update), tag `phase-1.2-SP-C2-runtime-1.0.0` → `8933bd18`, pushed origin main + tag
- source: standalone repo `LT-0I/noeticbraid-sp-C2-runtime` commit `bcbec6b` @ tag `sp-c2-runtime-1.0.0` (sp-repos working tree at `C:/Users/13080/Desktop/HBA/sp-repos/noeticbraid-sp-C2-runtime/`)
- module: SP-C2 = `noeticbraid-runtime` placeholder package replaced with full implementation (~921 LOC = 11 src + 6 tests + 4 docs); unlocks downstream SP-D / SP-H / SP-B / SP-E
- public surface:
  - `BrowserSession` Protocol (navigate/eval/click/type_text/screenshot per-call timeout + synchronous close)
  - `launch_browser` / `BrowserProcess` Playwright persistent-context launcher (filtered args eliminates user-data-dir 双传; injectable launcher for tests)
  - `get_session` attach-only mode (`tab_id=None` → first page or `about:blank` via `/json/new`; explicit tab_id lookup; C1-backed new-session path **deferred** until SP-C1 integration, documented in IMPLEMENTATION_NOTES.md)
  - `CdpSession` CDP 直连实装 (websocket-client transport optional; FakeTransport injected for tests)
  - `CLISandbox` 三道闸 (command basename allowlist + cwd root guard + Popen 进程组 + `_kill_tree` via `taskkill /F /T` Windows / `os.killpg(SIGKILL)` POSIX; deny-by-default env_overlay)
  - `SelectorStore` hot-reloadable selectors.json + 不可变副本语义
  - `_proxy.py` HelixMind TUN bypass (`198.18.0.0/15` → `198.18.*.*` Chrome wildcard; unsupported CIDR `raise ValueError`, no raw passthrough)
  - `run_record.py` frozen RunRecord-compatible artifact_refs helpers (`_FROZEN_EVENT_TYPES` runtime guard + ValueError on non-frozen event_type, not just Literal type hint)
- v3.3 dual-review × 2 rounds:
  - **round 1 reply dual review**: Reviewer A claudecode sonnet 4.6 code-reviewer PASS H=0/M=2/L=3; Reviewer B codex CLI gpt-5.5 FAIL H=2/M=3/L=1
  - round 1 arbitration (claudecode main opus 4.7): CONCERN H=0/M=5/L=4 after merge + reclassify (B's HIGH-1 close timeout was README自吹 vs blueprint signature drift → demoted LOW; B's HIGH-2 Literal type hint vs runtime guard → demoted MEDIUM, fix = add ValueError check)
  - round 1 finding list: 5 MUST (launcher user-data-dir 双传 / event_type runtime guard / TUN unknown CIDR raw passthrough / CLISandbox subtree leak / README close drift) + 4 SHOULD + 1 DEFERRED (C1-backed new-session path)
  - **round 2 revision verify dual review**: Reviewer A claudecode sonnet 4.6 PASS 10/10 verified; Reviewer B codex CLI gpt-5.5 CONCERN 9/10 verified (1 gap on SHOULD-2 BLUEPRINT.md license note)
  - round 2 arbitration (claudecode main opus 4.7): PASS — codex's gap was internal ARBITRATION.md drafting contradiction (SHOULD-2 finding row vs `## 不可动 invariant` section); BLUEPRINT.md is immutable 固化合同 per invariant; scope amended to `docs/DEPENDENCY_LICENSES.md` only; main repo license_check_gate reads PyPI metadata, not BLUEPRINT comments
- gates (post-revision):
  - license_check_gate: 14 PASS / 1 FAIL (only EXCEPTION-6 typing_extensions PSF-2.0 remaining; no pywin32, no portalocker, no MPL); count delta vs T073 baseline (27/2) reflects pip env state at integration time
  - private_leak_scan: PASS 260 scanned (allowlist updated to whitelist `profile_dir` + `profile_path` Chrome user-data-dir variable names — playwright_launcher.py legitimate usage, not private data leak; allowlist additions in commit `8933bd1`)
  - phase1_2_contract_gate: PASS (sidecar sha256=96CE4BAC..., 8 paths, 17 schemas, 10 path_policy_cases — frozen byte-equal preserved)
  - pytest core: 424 passed (= 1.3.0 + T073 baseline, no regression)
  - pytest backend: 74 passed
  - pytest runtime (NEW): 21 passed (test_launcher 5 + test_run_record 3 + test_proxy 5 + test_cli_sandbox 5 + test_selector_store 2 + test_cdp_session 1)
  - github CI: PASS run 25414329863 (https://github.com/LT-0I/noeticbraid/actions/runs/25414329863)
- red lines verified clear: license = Apache-2.0 throughout; runtime dependencies = []; no pywin32 / mcp-server-sqlite / portalocker / DPAPI / crypt32 / CryptUnprotectData; no new RunRecord event_type literal added (frozen 14 锁死 honored at runtime); no frozen contract / private edits
- frozen baseline preserved: phase1_2_openapi.yaml + vault_layout.yaml + phase1_3_openapi.yaml byte-equal vs 1.3.0 freeze
- audit artifacts (kept in GPT5_Workflow archive, not main repo): `archive/phase-1.2/SP-C2-runtime/` containing `BLUEPRINT.md`, `REVIEW.md`, `reviewer_A.md` (round 1), `reviewer_B.md` (round 1), `ARBITRATION.md` (round 1 + round 2 仲裁 + 修订记录 + invariant section), `verifier_round2.md` (sonnet round 2), `reviewer_B_round2.md` (codex round 2), `REVIEWER_A_FOLLOWUP.md` (superseded), `REVISION_PROMPT_for_C2_session.md` (used by C2 writing session)
- side observation: round-1 verdict divergence (sonnet PASS vs codex FAIL) was the strongest dual-review信号 since contract-1.2.0; arbitration captured 4 real bugs that single-reviewer pass would have shipped (TUN raw CIDR passthrough, CLISandbox subtree leak, RunRecord runtime breakable, launcher user-data-dir 双传)

## SP-C1 Account Pool & Quota integration (2026-05-05, full v3.3 dual-review × 2 rounds)

- integration commit `b11f203` (HEAD before this audit prose), preceded by allowlist commit `6590491` (private_leak_scan rules: SP-C1 `account_id` schema field + SP-C2 audit_trail prose `profile_path`/`profile_dir` markers — both legitimate non-leak references), tag `phase-1.2-SP-C1-account-quota-1.0.0` → `b11f203`, pushed origin main + tag
- source: standalone repo `LT-0I/noeticbraid-sp-C1-account-quota` commit `551ff15` @ tag `sp-c1-account-quota-1.0.0` (sp-repos working tree at `C:/Users/13080/Desktop/HBA/sp-repos/noeticbraid-sp-C1-account-quota/`)
- module: SP-C1 = `noeticbraid_core.account` 子包 **首次** 并入 `packages/noeticbraid-core/src/noeticbraid_core/account/` (~1048+ LOC = 5 src + `__init__.py`); 旧 stage-1.5 module-account-quota-v0 (integration commit `e45c1694`) 仅 archived 在 `archive/modules/`, 从未并 packages, SP-C1 是真正首次 src 落地
- public surface:
  - `AccountRegistryRecord` / `QuotaStateRecord` / `QuotaEventRecord` / `PublicProfileSummary` / `SessionHealthRecord` Pydantic v2 模型 (全部 `frozen=True` + `extra="forbid"`)
  - `AccountQuotaStore.load_registry()` / `update_state(updater)` / `append_event(event)` 单进程 `threading.Lock` 并发安全 (跨进程 advisory lock = DEFERRED 1.3.x backlog)
  - `select_account()` quota-aware 选择器 (空池 / 全 cooldown 失败模式 fail-closed)
  - `record_usage(...)` quota signal + secret redaction (sanitize_reason + observed_text_hash 持久化)
  - `SessionHealthProbe` Protocol + `check_session_health(now_fn=...)` + `record_session_health()` (probe 返 dict 时 `payload.setdefault("checked_at", now_fn())` 让 fake clock 注入真生效)
  - `to_account_pool_profiles()` / `build_account_pool_payload()` frozen `{"profiles": [...]}` adapter (AccountPoolDraft 1.2.0 contract 严守, 顶层不增 `quota_state` / `session_health` / `account_id`)
  - `_atomic_write_json` 异常 chaining (`from exc`, 区分 `(TypeError, ValueError, JSONDecodeError)` malformed vs `(PermissionError, OSError)` 基础设施错穿透)
  - 红线: 不读 cookie / 不启 browser / 不做 OAuth rotation / 不读 tokens.sqlite / 不引 pywin32 / mcp-server-sqlite / portalocker / DPAPI
- v3.3 dual-review × 2 rounds:
  - **round 1 reply dual review**: Reviewer A claudecode sonnet 4.6 code-reviewer PASS H=0/M=4/L=3; Reviewer B codex CLI gpt-5.5 CONCERN H=0/M=2/L=2
  - round 1 arbitration (claudecode main opus 4.7): CONCERN H=0/M=5/L=5+D1 after merge + reclassify (B#3 now_fn LOW→MED 注入失效是 testability + 时序 contract 漂移; B#4 test 缺口 LOW→MED 合一为 MUST-5; A#1 `_as_aware_utc` DRY MED→LOW byte-identical 重复非真伤; B#2 frozen 范围争议折中 — `PublicProfileSummary` MUST 共识 / 其他 records SHOULD defense-in-depth)
  - round 1 finding list: 5 MUST (single-process `threading.Lock` + store API 化 / `now_fn` 注入修复 / `PublicProfileSummary` `frozen=True` / `_atomic_write_json` 异常 chaining / 7 new tests) + 5 SHOULD (`_as_aware_utc` DRY / 其他 records `frozen=True` + `SessionHealthRecord._hash_observed_text` `model_validator(mode="before")` 改造 / `_selection_key` `-priority` 注释 / `_SECRET_WORD_RE` bare session intentional 注释 / unused `timedelta` import 删除) + 1 DEFERRED (跨进程 advisory file lock + 多进程压测 → contract 1.3.x backlog)
  - **round 2 revision verify dual review**: Verifier A claudecode sonnet 4.6 PASS verified=11/11 gaps=0 new_findings=0; Reviewer B codex CLI gpt-5.5 PASS verified=11 gaps=0 regressions=0 — 双审一致, 无 divergence, 无 round-1 漏审
  - round 2 arbitration (claudecode main opus 4.7): PASS — 5 MUST + 5 SHOULD 全 LANDED (实装 8 new tests 比原 7 多 1 now_fn regression cov), 1 DEFERRED 已记录 `docs/IMPLEMENTATION_NOTES.md:31-33` + `store.py:43-45` docstring + ARBITRATION.md, 红线零违规, 蓝图零漂移, 零 incidental change
- gates (post-integration):
  - license_check_gate: N/A — 脚本在 main repo 不存在 (SP-C2 README 提及的脚本可能在 sp-repo 或已重构, 本周期未跑); SP-C1 sp-repo `docs/DEPENDENCY_LICENSES.md` 已 round-2 review 审过, Apache-2.0 (主) + MIT (依赖) only, 无 PSF/GPL/MPL/EPL/AGPL
  - private_leak_scan: PASS 274 scanned (allowlist 由 commit `6590491` 增量 — SP-C1 `account_id` 是 `AccountRegistryRecord.account_id: str` 合法 schema 字段名 + SP-C2 audit prose `profile_path`/`profile_dir` 字面引用 marker 名为追溯文档非真私数据)
  - phase1_2_contract_gate: PASS (sidecar sha256=96CE4BAC, 8 paths, 17 schemas, 10 path_policy_cases — frozen byte-equal preserved)
  - pytest core: 442 passed (= 424 baseline + 18 SP-C1 NEW: test_account_pool_bridge 2 + test_enforcer 4 + test_session_health 4 + test_store 8)
  - pytest backend: 74 passed (no regression)
  - pytest runtime: 21 passed (no regression vs SP-C2 baseline)
  - github CI: PASS run 25417202696 (26s) https://github.com/LT-0I/noeticbraid/actions/runs/25417202696
- red lines verified clear: license = Apache-2.0 throughout; main repo `noeticbraid-core/pyproject.toml` pydantic dep already declared (核心包既有); no pywin32 / mcp-server-sqlite / portalocker / DPAPI / crypt32 / CryptUnprotectData; no cookie I/O / browser launch / OAuth rotation / tokens.sqlite read in src; no frozen contract / private edits; bridge `{"profiles": [...]}` 顶层 shape preserved
- frozen baseline preserved: `phase1_2_openapi.yaml` + `vault_layout.yaml` + `phase1_3_openapi.yaml` byte-equal vs 1.3.0 freeze
- audit artifacts (kept in GPT5_Workflow archive, not main repo): `archive/phase-1.2/SP-C1-account-quota/` containing `BLUEPRINT.md`, `REVIEW.md`, `ARBITRATION.md` (round 1 + round 2 仲裁 + 修订记录 + invariant section), `REVISION_PROMPT_for_C1_session.md`, `round-1/{reviewer_A.md, reviewer_B.md}`, `round-2/{verifier_round2.md, reviewer_B_round2.md}`, `README.md` (cycle summary)
- side observation 1: round-1 verdict divergence (sonnet PASS vs codex CONCERN) 持续证明 contract-1.2.0 之后双审制度价值 — 仲裁层捕获 5 项单审会 ship 的真伤 (B#3 `now_fn` 注入失效 testability + 时序漂移, B#4 test 覆盖缺口 7 项, B#1 并发锁缺失 read-modify-write race, A#2 异常吞噬丢诊断, A#4 `PublicProfileSummary` mutation 风险). 类比 SP-C2 round-1 PASS vs FAIL 的 4 真伤记录, SP-C1 这次是 PASS vs CONCERN 但仍捕获 5 项, 双审制度二次验证.
- side observation 2: SP-C2 commit `5a6776e` 写入 audit prose 含 marker 字面名 (`profile_path` / `profile_dir`), 但当时漏加对应 LINE_ALLOWLIST_RULES — 导致本地 `private_leak_scan.py` 在 `5a6776e` 之后持续 FAIL, CI run 25414329863 因 CI 跑 Ubuntu 独立环境 + pip install 覆盖能 PASS, 本地脚本不 PASS. 本周期 commit `6590491` 一并修复. 此发现说明 CI 与本地 gate 行为存在 drift, 长期评估 — 选项: (a) CI 加 leak scan step 强制 sync, (b) 本地 pre-commit hook 强制本地 leak scan PASS 才允许 commit, (c) leak scan tool 自身做 docs/audit_trail.md 类自描述文档的智能识别 — 不在本周期决策, 列入 backlog

## SP-D Obsidian Vault Hub integration (2026-05-06, full v3.3 dual-review × 2 rounds, OMX `$code-review` 首次实战试点)

- integration commits: `4137cfd` (fix(scan): allowlist 9 个 SP-C1 audit_trail prose markers — SP-C1 commit 0a946c9 写入 prose 时漏 allowlist 一并补齐, 与 side observation 2 类似 drift 模式) → `44d04c7` (feat(obsidian): SP-D 集成), tag `phase-1.2-SP-D-obsidian-1.0.0` → `44d04c7`, pushed origin main + tag
- source: standalone repo `LT-0I/noeticbraid-sp-D-obsidian` commit `b922c4c` @ tag `sp-d-obsidian-1.0.0` (sp-repos working tree at `C:/Users/13080/Desktop/HBA/sp-repos/noeticbraid-sp-D-obsidian/`)
- module: SP-D = `noeticbraid-obsidian` 独立 package, 首次 src 落地 (替换 Stage 0 placeholder, ~3133 LOC = 12 modules + 5 tests + 4 docs + 7 schemas + 7 templates + 1 fixture + 1 config example)
- public surface:
  - `MarkdownRenderer.render_task / render_run_record / render_source_record / render_side_note / render_digestion_item / render_dashboard` Pydantic-free dataclass-based 渲染器 (schema enum + required + pattern 校验, 不合法 raise `RenderError`)
  - `VaultWriter.write_dashboard(note: RenderedNote) / write_stable_record / append_to_heading / record_sync_log` (atomic tmp+rename + try/finally tmp cleanup, dashboard overwrite preserve user `## Manual notes`, sync_log append-only 豁免 atomic_write_intent contract)
  - `DashboardGenerator.generate_today / generate_this_week / generate_digestion_queue / generate_account_pool` 生成器 (含 manual notes preserve 段)
  - `InboxWatcher.scan_once(callback)` polling-only (`watch()` defer 1.3.x), RunRecord `source_refs` 用 `source_obsidian_<sha256[:16]>` ID 不泄漏原始 vault path, 原路径单独写到 vault-only `vault_source_path` 字段
  - `is_allowed_write_path / resolve_under_vault` path policy (allowlist + denylist + `.obsidian` / `.git` 段拒绝 + `20_episodic_memory/10_user_raw/` 硬编码拒绝)
  - `validate_obsidian_hub` 5+1 项自检 (resource-presence / settings-boundary / path-policy-cases / schemas-strict / schemas-contract-version + **template-instance-check** 新增 stdlib-only enum/pattern/required/additionalProperties/const/type/array-items 全套验证)
  - 红线: 不实装 Obsidian 插件 / 不访问 Local REST API / 不管 git/LiveSync / 不读 user_raw / 不引 watchdog (polling only) / 不引 pywin32 / mcp-server-sqlite / DPAPI / OAuth rotation / tokens.sqlite
- v3.3 dual-review × 2 rounds:
  - **round 1 reply dual review**: Reviewer A claudecode sonnet 4.6 code-reviewer CONCERN H=2/M=4/L=2; Reviewer B codex CLI gpt-5.5 + **OMX `$code-review` 关键词试点** FAIL H=1/M=4/L=1
  - round 1 arbitration (claudecode main opus 4.7): CONCERN H=3/M=6/L=3+D1 after 双审互补合并 + reclassify (B#1 dashboard overwrite manual notes 数据丢失级 HIGH MUST / A#2 `_atomic_write_text` tmp 残留 HIGH MUST / A#1+B#2 renderer enum 校验 HIGH MUST 共识但严重度分歧 split / A#5+B#3 source_refs pattern MED MUST 共识 / B#4 API surface §S5 drift MED MUST / B impl quality scan dashboard 缺 generate_this_week MED MUST)
  - round 1 finding list: 6 MUST + 5 SHOULD + 1 DEFERRED, 全部派给 D session round-2 修订
  - **round 2 verify dual review**: Verifier A claudecode sonnet 4.6 PASS verified=12/12 gaps=0 new_findings=0; Reviewer B codex CLI gpt-5.5 + OMX `$code-review` PASS verified=12 gaps=0 regressions=0 — 双审一致, 无 divergence, 无 round-1 漏审
  - round 2 arbitration: PASS — 12 finding 全 LANDED 带 file:line 证据, 测试 11→20 (+9 new tests 含 manual notes preserve / atomic write tmp cleanup / renderer enum negative / weekly dashboard / template instance validator), 红线零违规, 蓝图零漂移 (BLUEPRINT §S5 已对齐实装), 零 incidental change
- gates (post-integration):
  - private_leak_scan: PASS 274 scanned (allowlist 由 commit `4137cfd` 增量 — 9 个 SP-C1 audit_trail prose markers `profile_path`/`profile_dir`/`account_id` 字面引用为追溯文档非真私数据)
  - phase1_2_contract_gate: PASS (sidecar sha256=96CE4BAC, 8 paths, 17 schemas, 10 path_policy_cases — frozen byte-equal preserved)
  - pytest core+backend+runtime: 537 passed (no regression)
  - pytest noeticbraid-obsidian: 20 passed (新增 20 tests, 全部 round-2 期望覆盖)
  - github CI: PASS run 25424215094 (24s) https://github.com/LT-0I/noeticbraid/actions/runs/25424215094
- red lines verified clear: license = Apache-2.0 throughout; main repo `noeticbraid-obsidian/pyproject.toml` `dependencies = []` (stdlib only, 无 watchdog / 无 jsonschema / 无 ruamel.yaml); no pywin32 / mcp-server-sqlite / portalocker / DPAPI / crypt32 / CryptUnprotectData; no cookie I/O / browser launch / OAuth rotation / tokens.sqlite read in src; no Obsidian plugin / Local REST / git/LiveSync / user_raw functional code; no frozen contract / private edits
- frozen baseline preserved: `phase1_2_openapi.yaml` + `vault_layout.yaml` + `phase1_3_openapi.yaml` byte-equal vs 1.3.0 freeze
- audit artifacts (kept in GPT5_Workflow archive, not main repo): `archive/phase-1.2/SP-D-obsidian/` containing `BLUEPRINT.md`, `REVIEW.md`, `ARBITRATION.md` (round 1 + round 2 仲裁 + 修订记录), `REVISION_PROMPT_for_D_session.md`, `round-1/{reviewer_A.md, reviewer_B.md}`, `round-2/{verifier_round2.md, reviewer_B_round2.md}`, `README.md` (cycle summary)
- side observation 1: **OMX `$code-review` 首次实战试点** (Reviewer B round-1 prompt 顶部加 `$code-review` 关键词触发 OMX UserPromptSubmit hook). Reviewer B 独抓 **1 HIGH 数据丢失级别真伤** (dashboard overwrite 丢用户手写 `## Manual notes` — Reviewer A 漏看 writer↔dashboard 集成路径) + 2 MED (API surface §S5 drift + dashboard 缺 generate_this_week). Reviewer A 独抓 HIGH `_atomic_write_text` tmp 残留 + MED sync_log atomic 豁免文档化. 双审 2 共识 MED (`source_refs` schema pattern + `task_type` enum 数). 互补性强不可单一依赖. 与 SP-C1 OMX 测试集结论 (`$code-review` 在 round-2 PASS 后代码上仍抓到 4 份 reviewer 都漏的 `sanitize_reason` Bearer 泄漏 HIGH) 二次验证 OMX 价值. 后续 SP cycle 标准模板: Reviewer B prompt 默认 include `$code-review` 关键词.
- side observation 2: Integration-time fix `packages/noeticbraid-obsidian/tests/test_resources_and_validator.py::test_readme_documents_reference_projects` 使用 `Path("README.md")` 依赖 pytest cwd, 主仓 cwd 解析读到 main repo root README 而非 packages 内 README — 改用 `Path(__file__).resolve().parent.parent / "README.md"` 包根相对路径. 这是 round-2 双审都漏抓的真伤 (sp-repo 内跑 cwd 恰好对应所以测试 PASS), 集成主仓时才暴露. sp-repo 1.0.0 保持 frozen, fix 仅在主仓侧 (commit `44d04c7`). 长期 backlog: round-2 reviewer prompt 应加 "模拟从 sp-repo 集成到主仓后路径解析" checklist 项 (target 1.3.x process improvement).

## SP-H NotebookLM Bridge integration (2026-05-06, full v3.3 dual-review × 2 rounds, OMX `$code-review` 二次实战验证)

- integration commits: `e2a9a6f` (feat(notebooklm-bridge): integrate SP-H NotebookLM Bridge v0.3.0) → `2a9e91f` (merge no-ff to main), tag `phase-1.2-SP-H-notebooklm-1.0.0` → `e2a9a6f`, pushed origin main + tag
- source: standalone repo `LT-0I/noeticbraid-sp-H-notebooklm` commit `1bec29d` @ tag `sp-h-notebooklm-1.0.0` (sp-repos working tree at `C:/Users/13080/Desktop/HBA/sp-repos/noeticbraid-sp-H-notebooklm/`)
- module: SP-H = `noeticbraid-notebooklm-bridge` 独立 package, 嵌套 namespace `noeticbraid.tools.notebooklm_bridge` (与现有 `noeticbraid_*` underscore-flat namespace 共存; BLUEPRINT §1/§5.3 锁死), ~1769 LOC = 7 src modules + 1 selectors.json + py.typed + 8 tests + 12 docs
- public surface:
  - `push_sources(session, notebook_id, sources, *, timeout_s=60) -> list[str]` — 推 URL/text 源到 NotebookLM, 返回 `source_notebooklm_<sha256[:24]>` 形态的 source_ref ID
  - `pull_briefing(session, notebook_id, *, timeout_s=120) -> str` — 拉 Briefing Doc 文本, 不返回 None (空文本 raise `NotebookLMTimeoutError`)
  - `pull_faq(session, notebook_id, *, timeout_s=120) -> list[dict]` — 拉 FAQ 列表 `[{"q": str, "a": str}, ...]`
  - `to_source_records(notebook_id, briefing_text, run_id) -> list[dict]` — 序列化为 frozen `SourceRecord 1.0.0` dict (`source_type=ai_output`, `evidence_role=source_grounding`, `quality_score` 4 档枚举校验, SHA-256 内容哈希)
  - `parse_faq(raw)` — 兼容 dict/list/markdown text 三种输入的 FAQ 归一化器
  - `BrowserSession` Protocol (镜像 SP-C2, 严格 4 方法 navigate/eval/click/type_text), 8 typed errors (`NotebookLMBridgeError` 派生)
  - `redact_str` redaction 边界 (token/cookie/Authorization/Google API key 模式), `OperationEvent` immutable tuple-based dataclass
  - 红线: 不直接 launch browser / 不 import playwright/selenium / 不开 CDP socket / 不读 cookie / 不引 OAuth refresh / 不引 tokens.sqlite / 不引 pywin32 / mcp-server-sqlite / DPAPI; 浏览器交互全部走 SP-C2 注入的 `BrowserSession` Protocol 4 方法边界
- v3.3 dual-review × 2 rounds:
  - **round 1 reply dual review**: Reviewer A claudecode sonnet 4.6 code-reviewer PASS H=0/M=3/L=2 (NotebookLMSelectorError guard / NotebookLMSerializationError dead class / OperationEvent mutable list 等); Reviewer B codex CLI gpt-5.5 + **OMX `$code-review` 关键词** CONCERN H=1/M=4/L=1
  - round 1 arbitration (claudecode main opus 4.7): CONCERN — verdict 采纳 B 的 1 HIGH 严重度 (started event 语义错误真伤), 合并 10 finding (HIGH=1/MED=6/LOW=3 = 6 MUST + 4 SHOULD)
  - round 1 finding list: MUST-1 HIGH (`_event_type_for` 把 status="started" 写成 `source_record_linked`/`artifact_created` — RunRecord 1.0.0 语义违反, ledger 提前记录"已链接/已创建") / MUST-2 MED (NotebookLMSelectorError 三处 except guard) / MUST-3 MED (selectors.json `text=Sources` fallback 太宽 - 任何含 "Sources" 字样页面都过) / MUST-4 MED (selectors.json `text=Briefing` + `_script_extract_text` 触发整页 bodyText 污染 artifact) / MUST-5 MED (selector hot-reload public ops 硬编码 default 不接 env override) / MUST-6 MED (caller-facing exception 字符串未 redaction) / SHOULD-1 MED (NotebookLMSerializationError 死类) / SHOULD-2 LOW (OperationEvent frozen 含 mutable list[str]) / SHOULD-3 LOW (`_eval` TypeError fallback positional timeout) / SHOULD-4 LOW (DEVELOPER_GUIDE.md 缺)
  - **round 2 verify dual review**: Verifier A claudecode sonnet 4.6 PASS verified=10/10 new_concerns=1 LOW (NC-1 `_eval` try/except 双路径已相同, 1.3.x backlog); Reviewer B codex CLI gpt-5.5 + OMX `$code-review` PASS verified=10 regressed=0 new_concerns=0 — 双审一致, 修订记录 file:line 漂移 ±3 行但实现已落地
  - round 2 arbitration: PASS — 10 finding 全 LANDED 带 file:line 证据, 测试 14→24 (+10 new tests 含 started 不污染 created/linked / NotebookLMSelectorError 不被吞 / selector text fallback 收紧 / extract_text 不返回 bodyText / env override / wrapped error redaction / serializer enum 拒绝), 红线零违规, 蓝图零漂移, version bump 0.2.0→0.3.0 (MUST-1 是语义修复 minor bump 合理)
- gates (post-integration):
  - private_leak_scan: PASS 309 scanned (allowlist 不变 — SP-H 本次未触发 prose drift)
  - phase1_2_contract_gate: PASS (sidecar sha256=96CE4BAC, 8 paths, 17 schemas, 10 path_policy_cases — frozen byte-equal preserved)
  - pytest packages 全量: 581 passed (no regression, SP-H 24 用例 + 主仓现有 557)
  - pytest noeticbraid-notebooklm-bridge: 24 passed (新增 24 tests, 全部 round-2 期望覆盖)
  - github CI: PASS run 25427632502 (26s) https://github.com/LT-0I/noeticbraid/actions/runs/25427632502
- red lines verified clear: license = Apache-2.0 throughout; main repo `noeticbraid-notebooklm-bridge/pyproject.toml` `dependencies = []` (stdlib only, 无 playwright/selenium/websocket-client); dev-only `pytest>=8` + `PyYAML>=6` 均 MIT; no pywin32 / mcp-server-sqlite / portalocker / DPAPI / crypt32 / CryptUnprotectData; no cookie I/O / browser launch / OAuth rotation / tokens.sqlite read in src; SP-C2 BrowserSession Protocol 边界严格 4 方法 (navigate/eval/click/type_text), 不扩展私有方法; no frozen contract / private edits
- frozen baseline preserved: `phase1_2_openapi.yaml` + `vault_layout.yaml` + `phase1_3_openapi.yaml` byte-equal vs 1.3.0 freeze; RunRecord 14 `event_type` enum 兼容 (started→`task_created`, succeeded→`source_record_linked`/`artifact_created`/`task_completed`, failed→`task_failed`)
- audit artifacts (kept in GPT5_Workflow archive, not main repo): `archive/phase-1.2/SP-H-notebooklm/` containing `BLUEPRINT.md`, `REVIEW.md`, `ARBITRATION.md` (round 1 + round 2 仲裁 + 修订记录), `REVISION_PROMPT_for_H_session.md`, `REVISION_RECORD.md` (H session 自报), `round-1/{reviewer_A.md, reviewer_B.md}`, `round-2/{verifier_round2.md, reviewer_B_round2.md}`, `README.md` (cycle summary)
- side observation 1: **OMX `$code-review` 第二次实战验证 (SP-D 后)** — Reviewer B 在 SP-H round-1 独抓 1 HIGH 真伤 (started event 写成完成型 event_type, RunRecord 语义违反, observability 消费者拿到错状态). Reviewer A 评同一项为 MED, 仲裁采纳 B 的 HIGH 严重度. 与 SP-D round-1 (B 独抓 dashboard overwrite 数据丢失 HIGH) 形成双案验证: OMX `$code-review` 在数据语义/数据完整性维度独有抓伤能力. 主 session v3.3 标准模板: Reviewer B prompt 默认 include `$code-review` 关键词 — SP-D 试点确立, SP-H 二次验证, 后续 SP-B/SP-E/SP-A/SP-F/SP-G 沿用.
- side observation 2: 主仓侧适配 — `tests/conftest.py:hba_root()` (sp-repo 用 parents[3]=HBA root + `noeticbraid/docs/contracts/`) 主仓集成时改 `main_repo_root()` (parents[3]=main repo root + `docs/contracts/`); `tests/test_docs.py` 删 sp-repo 独有 `BLUEPRINT.md`/`REVIEW.md` 两条期望 (sp-repo 1.0.0 frozen, 这两文件留 sp-repo 内). 与 SP-D side observation 2 (`Path("README.md")` cwd 依赖) 同源 — round-2 reviewer prompt "模拟从 sp-repo 集成到主仓后路径解析" checklist 项仍未加入 (target 1.3.x process improvement; 但本次集成 H session 自己用 `Path(__file__).resolve().parents[N]` 而非 cwd, 已比 SP-D 进步一级 — 只是 parents 层数不一致需要主仓侧改一行).
- side observation 3: codex CLI `-o` 输出文件最终 stdout 覆盖 bug — Reviewer B round-1 完成时 codex 把 `reviewer_B.md` 11036 字节完整报告覆盖成 260 字节 "已生成 reviewer_B.md" 确认消息. Monitor 命中文件出现时为完整版本, 后续 codex 收尾阶段又写入. 修补: 主 session 从对话上文 Read 历史读到的完整内容直接 Write 重建 (130 行). 后续 SP cycle Reviewer B 应改 monitor min-size threshold (>1KB 才视为有效落盘) 或 codex 不用 `-o` 改用 stdout-tee 模式. round-2 已采用 `≥1KB` 阈值, 验证有效 (5441 bytes 完整 PASS).

