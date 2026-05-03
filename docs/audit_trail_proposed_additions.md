# Audit Trail — Proposed Additions (Pending Decision)

> **WARNING — DO NOT APPEND VERBATIM TO `audit_trail.md`.**
>
> This file is **not** to be appended to `audit_trail.md` verbatim. It is a
> **pending-decision register** for 4 modules currently lacking noeticbraid
> git anchoring (no real merge commit, no tag, no audit_trail row). Final
> disposition pending main session decision per `FOLDER_REORG_PROPOSAL.md`.
> Per codex Reviewer B (track_B.md §4): proposed rows here are not comparable
> to existing final `PASS` / `PROCEED with fixes` audit_trail rows — they are
> pending/process notes, not completed v3.3 dual-review milestones, and do
> not link to real noeticbraid commits/tags.

These rows document the 4 modules that completed parts of v3.3 8-step but were
**not committed to noeticbraid**. Each module passed local TDD red→green and
validators; integration_report.md confirms files installed under
`GPT5_Workflow/tools/<name>/` rather than `noeticbraid/packages/`. Once the
main session decides whether to migrate these modules into noeticbraid, real
Merge SHA / Tag must be assigned and the rows then re-evaluated against the
audit_trail.md "dual review evidence" criterion (which 2/4 modules currently
fail because they have no Reviewer A artifact).

Header columns match `docs/audit_trail.md` line 9 format exactly:

| Phase | Stage | PR | Merge SHA | Tag | Claude Review | Codex Review | Verdict |
|---|---|---|---|---|---|---|---|
| 1.2 | Module multimodel-alliance extension | - [a] | - [a] | - [a] | GPT5_Workflow archive/modules/module-multimodel-alliance/reviews/reviewer_A.md (CONCERN-class, claudecode sonnet 4.6) | GPT5_Workflow archive/modules/module-multimodel-alliance/reviews/reviewer_B.md + reply_reviewer_B.md (CONCERN, codex) | TOOLS-ONLY (no v3.3 step 7 to noeticbraid; pending main session migration decision; see FOLDER_REORG_PROPOSAL.md). Local evidence: integration_report at GPT5_Workflow archive/modules/module-multimodel-alliance/integration_report.md (validator PASS 3 fixtures, pytest 7 PASS); 5 deferred follow-ups (capability-to-role enforcement / failure_recovery fixture / aggregation provenance / full JSON Schema validator / token cost spec). Location: GPT5_Workflow/tools/multimodel_alliance/ (not yet in noeticbraid git tree) |
| 1.2 | Module obsidian-hub extension | - [a] | - [a] | - [a] | **(no Reviewer A artifact in v3.3 archive)** — rationale: archived module entered local integration without Reviewer A round; only Reviewer B (codex) evidence exists. See codex track_B.md §1 bullet 2. | GPT5_Workflow archive/modules/module-obsidian-hub/reviews/reviewer_B.md + reply_reviewer_B.md (CONCERN, codex) | TOOLS-ONLY (no v3.3 step 7 to noeticbraid; pending main session migration decision; see FOLDER_REORG_PROPOSAL.md). Local evidence: integration_report at GPT5_Workflow archive/modules/module-obsidian-hub/integration_report.md (validator PASS 8 checks: expected-files / settings-boundary / path-policy-cases / schemas / template-frontmatter-anchors / fixture-frontmatter / text-safety / no-real-vault; pytest 11 PASS); 3 integration fixes (validator cache ignore / source_record schema source_ref+external_url / no-real-vault text scan); state.json marks step=archived (commit/tag/push gate explicitly blocked because GPT5_Workflow is not a git repo). Location: GPT5_Workflow/tools/obsidian_hub/ (not yet in noeticbraid git tree) |
| 1.2 | Module workflow-scheduler-telegram extension | - [a] | - [a] | - [a] | GPT5_Workflow archive/modules/module-workflow-scheduler-telegram/reviews/reviewer_A.md + reply_reviewer_A.md (CONCERN-class, claudecode sonnet 4.6) | GPT5_Workflow archive/modules/module-workflow-scheduler-telegram/reviews/reviewer_B.md + reply_reviewer_B.md (CONCERN, codex) | TOOLS-ONLY (no v3.3 step 7 to noeticbraid; pending main session migration decision; see FOLDER_REORG_PROPOSAL.md). Local evidence: integration_report at GPT5_Workflow archive/modules/module-workflow-scheduler-telegram/integration_report.md (pytest 10 PASS; red-check 3 expected failures → green 3 PASS); 4 arbitration fixes (runner status state machine pending→running→completed/failed/blocked / shared JSONL events.py emit() schema / Telegram hourly rate cap + disabled-by-default / Python>=3.9 enforcement via compat.py). Location: GPT5_Workflow/tools/workflow_scheduler_telegram/ (not yet in noeticbraid git tree) |
| 1.2 | Module bestblogs-info-tracking extension | - [a] | - [a] | - [a] | **(no Reviewer A artifact in v3.3 archive)** — rationale: archived module entered local integration without Reviewer A round; only Reviewer B (codex) evidence exists. See codex track_B.md §1 bullet 2. | GPT5_Workflow archive/modules/module-bestblogs-info-tracking/reviews/reviewer_B.md + reply_reviewer_B.md (CONCERN, codex) | TOOLS-ONLY (no v3.3 step 7 to noeticbraid; pending main session migration decision; see FOLDER_REORG_PROPOSAL.md). Local evidence: integration_report at GPT5_Workflow archive/modules/module-bestblogs-info-tracking/integration_report.md (red-check 5 failed 8 passed → final pytest 13 PASS; validator PASS); 5 integration fixes (URL `auth` path-segment + query-key matching / tracking_run.source_count == len(source_ids) validator + fixture corrected 4→3 / RSS fetch follow_redirects=False + 3xx rejection / content_type schema-enum normalization ARTICLE/PODCAST/VIDEO/TWEET / `.git` private marker regex `(?:^|[\\/])\\.git(?:[\\/]|$)`). Location: GPT5_Workflow/tools/bestblogs_info_tracking/ (not yet in noeticbraid git tree) |

[a] PR / Merge SHA / Tag intentionally `-` — module never reached v3.3 step 7
(commit + tag + push to noeticbraid). These cells will only become populated
if and when main session approves migration into the noeticbraid git tree.
