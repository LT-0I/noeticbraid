# Phase-1 MUP Gate Record

> **STATUS: PHASE-1 MUP — NOT YET COMPLETE.** Gate record as of **2026-05-15 (δ demo day-3/14)**.
> 4 of 5 v3.2 §10.4 criteria met at the test/contract layer (criterion 1 *partially*); criterion 2 (§10.2 demo) is **observation-gated and PENDING** until the 14-day window closes **2026-05-26**.
> This document is the auditable evidence ledger for the v3.2 §10.4 "第一阶段 MUP 范围裁决" completion criteria. It does **not** assert completion. The real `phase-1-MUP-complete` tag is deferred to ≥2026-05-26 and is additionally gated on the criterion-1 disposition in §6.

- Repo: `/home/l1u/workspace/noeticmind/noeticbraid`
- HEAD at record time: `eb9f295` (this record lands on the next commit)
- Spec source of truth: `PROJECT_DEFINITION_v3.2.md` §10 (双 demo 验收) + §10.4 (MUP 范围裁决) + §11.b / §11.b.S
- Authoring discipline: synthesis by main session; evidence gathered + cross-checked by an independent read-only verification agent (§5); record independently audited by codex (gpt-5.5 xhigh), verdict APPROVE-WITH-MINOR, all MINORs folded (§5).

---

## 1. v3.2 §10.4 completion criteria (blueprint lines ~356–362)

1. OMC demo 全部 acceptance 通过（§10.1）
2. AI 旁注追踪 demo 全部 acceptance 通过（§10.2 + §11.b.S）
3. 4 个未入库模块归属裁决记录在案
4. 首批 4 端基础 health-check 可见
5. 一次手工触发的对抗辩论跑通 + 写入 candidate 区可被独立检查

> §10.4 line 363: **"任何超出此范围的事都不进第一阶段验收"**. §10.4 line 344: OMC demo "✅ 必须完整完成". §10.3 line 333: AI 旁注 demo 周期 = "14 天连续运行". §10.4 line 345: "AI 旁注追踪 demo 14 天（§10.2）✅ 必须完整完成".

---

## 2. Verdict table

| # | Criterion | Verdict | Basis |
|---|---|---|---|
| 1 | §10.1 OMC demo acceptance | **PARTIALLY MET** | Engine plumbing proven via passing pytest at test/contract layer with seed/fixture data + deterministic extraction; no committed live-run "ignition" artifact. Consistent with §10.4 "minimum-demo-pass" framing but weaker than an observed live run. Disposition for the completion tag is explicit in §6 (not assumed). |
| 2 | §10.2 旁注 demo acceptance (+§11.b.S) | **PENDING (observation-gated)** | Build-complete + infra-ready (chain wired & CI-locked D6-01..04; §11.b.S landed D1-01; opt-out D2-05). Acceptance is **runtime-observational** over 14 days; window day-0=2026-05-12 → **day-14=2026-05-26**. Required artifacts (≥3 side-notes, ≥1 user response, all metadata-complete, zero tone_constraint violations) do not exist yet at day-3. |
| 3 | 4-module disposition recorded | **MET** | `noeticbraid-workflow/MODULE_VERDICTS.md` §1–§4 + summary table + δ status overview. |
| 4 | First-batch 4-end health-check visible | **MET** | SDD-D2-03 `f06b044` (+hotfix `1c17d5e` SDD-D2-03-hotfix-01); `capability_registry.py:22-43` 4 CLI ends; 9 real-health tests + 16 route tests pass. |
| 5 | Manual debate → candidate, independently inspectable | **MET** | SDD-D2-01 `e1649e5` (+hotfixes); manual-trigger gate enforced; writes `state/program_memory/candidates/multimodel_debate_candidates.jsonl` (candidate, not confirmed); 14 tests pass. |

**Overall: NOT COMPLETE.** Gate blocked on criterion 2 (observation-pending) and on the criterion-1 disposition (§6).

---

## 3. Evidence detail

### Criterion 1 — §10.1 OMC demo (PARTIALLY MET)
- (a) First visible project "吸收 OMC": `omc_workspace/project_store.py:16-17` `PROJECT_ID="omc-ingest"` / `PROJECT_TITLE="吸收 OMC"`, `_seed_help_lesson()`; SDD-D2-02 `b2ee841` (+CLI adopt hotfix `ce67256`). Tests: omc workspace routes/contract = 10 passed; `test_cli_adopt.py` = 8 passed.
- (b) External Reference Pool first entry: schema-level only (`workspace_project.py:29 external_reference_refs`; seeded in `project_store.py:69,84`). Per MODULE_VERDICTS §6.4 first-phase ERP scope is deliberately "schema + UI panel only" (no radar runtime) — a §10.4 descope, not a gap.
- (c) Candidate lesson batch: SDD-D3-01 `omc_knowledge_extractor.py` `499c335` (+hotfix `48a342d`) → deterministic L1–L5 lesson outline from real OMC source fixtures → candidate. `test_omc_knowledge_extractor.py` = **5 passed** (+ `test_omc_workspace_task_real_extraction.py`); codex fresh re-run of the criterion-1 suites = **38 passed** at HEAD `eb9f295`.
- (d) Capability registry first omc skills/agents: 5 capability entries (criterion 4 registry).
- (e) ≥1 real task using omc capability + R-6 reuse: SDD-D4-01 `801d562` (+hotfix `0ececb2`); `test_omc_task_reuse_loop.py` drives 3 submits → R6 gate `confirmed`, reuse_count 3, ledger refs; R6 gate global `test_r6_gate.py` = 12 passed.
- **Caveat / residual:** acceptance demonstrated through pytest with seeded/fixture data and deterministic extraction, **not** a captured end-to-end live OMC ingestion artifact. `.omx/artifacts/` untracked/empty; no committed runtime demo ledger. Engine ignition proven at test/contract layer only. The blueprint requires OMC demo "必须完整完成" (§10.4:344) — therefore this is a criterion that must be explicitly dispositioned before completion (§6), not silently waived.

### Criterion 2 — §10.2 旁注 demo (PENDING, observation-gated)
- Infrastructure complete: detector→SideNote→vault chain wired (SDD-D6-01..03) and cross-contract CI-locked (SDD-D6-04 `f32ba7d`); §11.b.S SideNote safety spec landed (SDD-D1-01 `059ef91`, contract 2.0.0); opt-out interaction (SDD-D2-05 `dbd5da4`).
- **Acceptance is NOT build-time.** §10.2 lines 317–323 require, over the 14-day run: ≥3 side-notes written by AI; ≥1 user response; all side-notes in the designated dir without altering user raw text (red line ①); all ≥3 with full metadata (evidence/type/confidence/tone_constraint); opt-out channel user-visible from the first note; zero tone_constraint violations.
- **Today is day-3.** None of the runtime-artifact criteria can be verified until the window completes **2026-05-26**. This criterion's closure is a future, dated obligation — not closeable now.

### Criterion 3 — 4-module disposition (MET)
- `noeticbraid-workflow/MODULE_VERDICTS.md` contains exactly 4 numbered dispositions: §1 `bestblogs_info_tracking` (archive + phase-2 RSS adapter); §2 `multimodel_alliance` (migrated to main repo); §3 `obsidian_hub` (migrated, §11.b.S hardening flagged); §4 `workflow_scheduler_telegram` (scheduler kept, Telegram→optional). Summarized at §5 table; dated 2026-05-11; cross-referenced from PROJECT_STATUS §0.0/§2/§7 + commit `d480246`.
- **Caveat:** file lives in sibling `noeticbraid-workflow/` (outside the git repo); no SHA-level versioning — auditability rests on that workflow dir's manifest. Ruling content is complete and recorded.

### Criterion 4 — 4-end health-check (MET)
- SDD-D2-03 `f06b044` (+hotfix `1c17d5e` SDD-D2-03-hotfix-01). `capability_registry.py:22-43` first-batch 4 ends: `cap_claude_code_cli`, `cap_codex_cli`, `cap_gemini_cli`, `cap_gemini_web`. A 5th `cap_chatgpt_web` was added later by SDD-D2-06 `0ac2e1a` (+its own hotfix `35f91a7` SDD-D2-06-hotfix-02) as `not_implemented` — outside first batch by MODULE_VERDICTS §6.3.
- Real health = subprocess `--version` probe, fail-soft (timeout/FileNotFound/nonzero/output-leak guarded), live-mode ledger artifact. `test_capabilities_real_health.py` = 9 passed; `test_capabilities_routes.py` = 16 passed; console `capabilities.tsx` + `routes.test.tsx`.
- **Caveat:** "basic" satisfied (startup-readable / version probe); web ends are placeholders by §10.4 design.

### Criterion 5 — manual debate → candidate (MET)
- SDD-D2-01 `e1649e5` (+hotfixes `c16bc88`/`785b738`/`04406f5`). `loop.py`, `candidate_store.py`, `ledger_bridge.py`, `convergence_markdown.py`.
- Manual-trigger enforced (`loop.py:69-77`; `test_loop_requires_manual_trigger`, `test_loop_rejects_b1_detector_auto_trigger_in_d2_01`); 3 adversarial roles; critical-objection blocks majority; 3–5 round cap.
- Writes candidate (not confirmed) to `state/program_memory/candidates/multimodel_debate_candidates.jsonl` (`candidate_store.py:18-24,87-91`); upgrade_rule "explicit user adoption OR reuse ≥3". `test_debate_loop.py`+`test_candidate_store.py`+`test_ledger_bridge.py` = 14 passed.
- **Caveat:** convergence driven by mock fixture; provider-mode added by hotfix-03 `04406f5` but the passing acceptance path uses the mock loop. Candidate-zone write contract + manual-trigger gate genuinely demonstrated.

---

## 4. Residual risks to true completion

| Risk | Severity | Disposition |
|---|---|---|
| Criterion 2 observation not yet run (day-3/14) | **Blocking** | Time-gated; closes 2026-05-26 if runtime artifacts satisfy §10.2 lines 317–323. Verify then. |
| Criterion 1 is minimum-demo-pass (test/contract layer), no committed live-run artifact | **Blocking until dispositioned** | Blueprint §10.4:344 requires OMC demo "必须完整完成". Before any completion tag this must be resolved one of two ways (see §6): (A) an explicit recorded ruling that §10.1 minimum-demo-pass = acceptance under the §10.4 MUP framing, or (B) a committed independently-re-inspectable live-run artifact. Not waived by default. |
| `MODULE_VERDICTS.md` outside git repo (no SHA versioning) | Low | Content complete; auditability via workflow-dir manifest. No action required for phase-1. |
| Live-run demo artifacts (ledger/candidate/health JSONL) untracked | Low/Medium | Behavior proven by automated acceptance tests; independent-inspectability met structurally. Consider committing sample artifacts at §10.2 close. |

---

## 5. Independent verification (dual-review)

- Evidence in §3 was gathered by an independent read-only verification agent (separate context), which re-ran the cited pytest suites at HEAD `eb9f295` and confirmed the SHAs exist in history. Verdicts: criterion 1 PARTIALLY MET, 3/4/5 MET, plus the cross-cutting "no committed live-run artifact" caveat — reflected above.
- This record was then independently audited by **codex (gpt-5.5, xhigh)**, verdict **APPROVE-WITH-MINOR**: it confirmed (a) the not-complete conclusion is evidence-correct, (b) no `phase-1-MUP-complete` tag may be cut now, (c) criteria 3/4/5 are materially supported (fresh pytest: crit-1 38 / crit-2-infra 26 / crit-4&5 30 passed), (d) §4.2.2–4.2.5 are correctly treated as v3.2 §10.4-deferred. Folded MINORs: corrected D2-03 hotfix SHA (`1c17d5e`, not `35f91a7`); corrected `test_omc_knowledge_extractor.py` count (5, not 7); made the §6 tag wording future-tense (tag not yet cut); made the criterion-1 completion precondition explicit and non-optional (§4 + §6).

---

## 6. Tag policy

- **On the commit that lands this record (δ day-3):** an honest milestone tag **`phase-1.2-mup-gate-day3` will be created** pointing at that commit. It asserts *"4/5 criteria met at test/contract layer; criterion 2 observation-pending; criterion 1 disposition open"* and is **explicitly NOT a completion tag**. (At record-authoring time this tag does not yet exist; it is created post-commit.)
- **Precondition for the real `phase-1-MUP-complete` tag (≥2026-05-26):** ALL of —
  1. §10.2 14-day window closed and runtime artifacts verified against §10.2 lines 317–323 (≥3 side-notes, ≥1 user response, full metadata, zero tone violations, user-raw untouched);
  2. Criterion 1 dispositioned by an explicit recorded decision — either (A) a ruling that §10.1 minimum-demo-pass evidence = acceptance under §10.4 MUP framing, or (B) a committed live-run artifact; the choice must be written down, not assumed;
  3. Criteria 3/4/5 still green at that HEAD.
- Until all three hold, only the non-completion milestone tag exists. The completion tag is a future, dated, conditioned obligation — **not granted by this record**.

---

*Record authored 2026-05-15 (δ demo day-3). Anchored to `PROJECT_DEFINITION_v3.2.md` §10 / §10.4 / §11.b.S. Independently audited (codex xhigh, APPROVE-WITH-MINOR; MINORs folded). No completion claimed.*
