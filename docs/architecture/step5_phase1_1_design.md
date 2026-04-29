# Phase 1.1 Stage 0 Design

- contract_version: 0.1.0
- status: DRAFT / non-authoritative
- generated_for: Round 1 / Step 5
- contract_owner: local_main_claude_session

## 1. Phase 1.1 scope and seven deliverables

Phase 1.1 is **Foundation Lock**. It exists to stop NoeticBraid from repeating the earlier structural drift: many schemas and reports existed, but the actual control plane did not consume them. Phase 1.1 therefore does not chase feature breadth. It locks the repository shape, authority boundaries, draft contracts, review flow, and the first implementation task chain.

The seven deliverables are:

1. **Repository layout and open/private boundary.** The open workspace lives under `packages/`, private material lives under `private/`, and legacy HelixMind assets live under `legacy/helixmind_phase1/` as read-only references. The old `state/` directory is gone, so the new architecture starts from an empty vault.
2. **Architecture and decision documentation.** Step 3 and Step 4 authority rules are documented, and the seven user decisions are split into separate `docs/decisions/D-Step4-*.md` files.
3. **Draft contract set.** Task, RunRecord, SourceRecord, ApprovalRequest, SideNote, and DigestionItem are represented in a strict non-authoritative stub, OpenAPI draft, and example fixtures.
4. **Obsidian Bridge interface placeholder.** Phase 1.1 must acknowledge Obsidian as storage without implementing vault writes too early. The bridge boundary and artifact resolver are documented; real writes wait for ModeEnforcer configuration and vault scanning.
5. **Run Ledger / Source Index vocabulary.** The Stage 0 contract defines the evidence vocabulary needed for later JSONL append and provenance tracking.
6. **CLI Runner and subprocess boundary.** Stage 0 records the command-registry and whitelist boundary, but it does not execute CLI AI tools.
7. **Web Console shell placeholders.** The Console package exists and can later consume OpenAPI/MSW mocks, but Stage 0 provides no UI implementation.

## 2. Why Stage 0 is separate from implementation

Stage 0 is a draft stage. It is not a coding sprint. The reason is authority: once multiple GPT sessions implement backend, guard, and Console tasks in parallel, they must share a frozen contract. If they start from a draft contract, every parallel branch will bake in slightly different assumptions. That creates merge failures and subtle behavioral drift.

The Stage 0 package therefore creates just enough structure for the local workflow to review, freeze, and broadcast contracts before parallel work. It also makes the local/remote split explicit: GPT-5.5 Pro Web produces project artifacts, while the local main Claude session owns workflow orchestration and contract freezing.

## 3. 1 + 1 + 3 execution structure

```text
Stage 0: GPT-5.5 Pro Web generates this draft package once.
Stage 1: GPT-A implements TASK-1.1.4 schemas.
Stage 2: GPT-B/C/D implement TASK-1.1.5/6/7 in parallel after schema 1.0.0 is frozen.
Stage 3: local integration merges, tests, and runs end-to-end smoke.
```

The first `1` is this package. The second `1` is GPT-A's schema implementation. The `3` are the parallel tasks for ledger/source index, guards/CLI stub, and Console shell. The shape is intentionally serial at the contract boundary and parallel only after that boundary is stable.

## 4. Contract freeze strategy

Stage 0 contracts are non-authoritative. GPT must not freeze them, mark them authoritative, or claim that fixtures are test baselines.

The local main Claude session owns contract freezing:

1. GPT-A implements schemas in `packages/noeticbraid-core/src/noeticbraid_core/schemas/**`.
2. Local Claude and Codex review the implementation.
3. If both reviews pass, local main Claude writes `frozen: true`, review commit hashes, and `contract_version: 1.0.0` into contract docs.
4. Local main Claude reverse-syncs implementation fields into the contract stub while stripping defaults, validators, `Field(...)`, and implementation methods.
5. Constraint details are downgraded into `CONTRACT_NOTE` comments and the API contract field table.
6. Local main Claude refreshes fixtures to `contract_version: 1.0.0` and `status: authoritative`.

Before this freeze commit, no downstream GPT should treat fixtures or draft schema as a baseline. After the freeze, changes require a contract change request.

## 5. Subtask map and write-boundary matrix

| Task | Stage | Purpose | Write boundary summary |
|---|---:|---|---|
| TASK-1.1.4 | 1 | Implement six Pydantic schemas | May write only core schema implementation and tests; cannot edit docs/contracts directly. |
| TASK-1.1.5 | 2 | Run Ledger JSONL append + Source Index | Placeholder only in Stage 0; full card issued by local session after schema freeze. |
| TASK-1.1.6 | 2 | ModeEnforcer + redline + CLI registry | Placeholder only in Stage 0; full card issued by local session after schema freeze. |
| TASK-1.1.7 | 2 | Console Shell + MSW mock | Placeholder only in Stage 0; full card issued by local session after schema freeze. |

The write boundaries are deliberately asymmetric. TASK-1.1.4 can implement schemas but cannot edit the contract stub. The local owner later reverse-syncs the implementation into the stub. This prevents GPT-A from prematurely freezing the contract or turning the stub into an implementation file.

## 6. Risk and pending items

Primary risks:

- schema implementation may diverge from draft intent;
- local freeze may forget to strip implementation constraints from the stub;
- fixtures may be mistaken for test baselines before `1.0.0`;
- private account fields may leak into open schema;
- Console implementation may begin before OpenAPI is frozen;
- browser-profile details may leak into public code;
- legacy state may be assumed even though old `state/` was deleted.

Mitigations:

- contract status is repeated in every contract document;
- fixtures contain `$schema_status: draft_nonbinding`;
- TASK-1.1.4 forbids direct edits to `docs/contracts/**`;
- gate scripts check required files and structure;
- the only ChatGPT placeholder is `Task.account_hint: Optional[str]`;
- private directories are excluded in `.gitignore`.

## 7. Phase 1.1 completion criteria

Phase 1.1 is complete only when the following are true:

- the monorepo/private directory structure is created;
- legacy is marked read-only;
- the contract has been frozen to `1.0.0` by the local owner after TASK-1.1.4 double review;
- Run Ledger and Source Index minimal implementation exists after TASK-1.1.5;
- ModeEnforcer blocks forbidden actions after TASK-1.1.6;
- Console shell consumes OpenAPI/MSW mock after TASK-1.1.7;
- Obsidian Bridge remains interface-only until vault scan and ModeEnforcer configuration are ready;
- gate scripts pass locally.

These completion criteria intentionally avoid Phase 1.2 / 1.3 implementation details. They define only the transition from Foundation Lock into Control Plane.

## 8. ChatGPT multi-account placeholder policy

User reality: the primary Phase 1.1 Web AI is ChatGPT and the user owns multiple ChatGPT accounts. However, the public schema must not contain real account-pool internals.

The only allowed Stage 0 schema placeholder is:

```python
Task.account_hint: Optional[str]
```

It means: “future Account Pool may use this as a routing hint.” It does not represent a real account identifier.

Forbidden in Stage 0 public schema:

- `chatgpt_session_cookie`;
- `cookie_jar_path`;
- `chatgpt_csrf_token`;
- `account_id` / `account_alias` / `subscription_tier`;
- `last_login_at` / `quota_window`;
- `profile_id` / `profile_dir`.

Those belong to Phase 1.2 / 1.3 private Account Pool and Browser Pool schemas.

## 9. Stage 0 output boundary

This package contains no schema business implementation, no ledger append implementation, no Console page implementation, no Playwright worker, no Obsidian writer, and no guard implementation. The only Python scripts are gate helpers. The Pydantic file under `docs/contracts/` is a strict stub, not a working implementation.

## 10. Why the first loop still has visible value

Although Stage 0 itself is not a user-facing product, it protects the first visible loop that will follow it. The first meaningful loop is Project Conversation Workspace → task classification → context building → single ChatGPT Web call → format convergence → run evidence → Obsidian artifact. The old implementation risk was that reports and data models could exist while the scheduler, router, and replayer did not consume them. This Stage 0 design prevents that by requiring every later implementation task to connect to the same draft contract vocabulary: tasks, runs, sources, approvals, side notes, and digestion items.

The first loop is intentionally single-model and ChatGPT-first. This does not contradict the long-term multi-model design. It creates a real browser-backed execution path before multi-model routing is enabled. A pure mock would prove only UI flow. An API-only call would not prove the user's subscription-web reality. A minimal ChatGPT Web profile proves that the system can begin removing manual transfer work while preserving Run Ledger evidence.

## 11. Open/private split in practical terms

The open side contains reusable mechanics: schema contracts, guards, state machines, Console shell, and generic bridge contracts. The private side contains personal operational material: browser profiles, account hints, provider-specific selector experiments, paid database scripts, private workflows, and user-specific prompt cards. This split matters because NoeticBraid may later open-source its core while keeping the user's actual automation surface private.

The Stage 0 directory tree deliberately keeps private folders visible but empty. That prevents later confusion about where sensitive files belong. It also allows `.gitignore` and future gate scripts to test that private directories exist but contain no publishable state. The package does not attempt to reconstruct the deleted legacy `state/` directory. DPAPI starts empty by design.

## 12. Contract owner handoff details

The contract owner rule is the most important Stage 0 authority boundary. GPT can draft contracts, but local Claude owns the freeze because the freeze commit is a workflow event, not just a file edit. It must combine review results, implementation field comparison, reverse-sync of stubs, fixture refresh, and version promotion into one atomic action. If GPT wrote `frozen: true` in Stage 0, downstream sessions would assume a stability that has not been earned.

The stub/implementation split is also intentional. The implementation file may use Pydantic v2 features such as `Field()`, defaults, validators, and business constraints. The docs contract stub may not. It exists as a readable cross-session contract surface. After local freeze, constraints are recorded as notes and tables, not executable validation code. That makes the stub stable for GPT-B/C/D while still letting the implementation be idiomatic.

## 13. How Stage 0 avoids Phase 1.2 leakage

The user has many ChatGPT accounts, but Stage 0 must not predefine the full account schema. Account Pool belongs to Phase 1.2 and Web AI Worker belongs to Phase 1.3. Stage 0 only reserves a single `account_hint` field because Project Conversation Workspace needs a future hook for route preference. It must not expose cookie paths, CSRF tokens, account aliases, profile directories, quota windows, or subscription tiers.

This keeps the public core clean. Account details will live in runtime/private layers and will be referenced indirectly through approved interfaces. If a later GPT tries to add private account fields to `Task`, local review should reject it as a boundary leak.

## 14. Gate-script philosophy

The gate scripts in Stage 0 are intentionally modest. They check that the required files and boundaries exist, not that the system works. The real implementation gates come later. This prevents the false confidence problem: a script that pretends to validate schema behavior before the schema is implemented would be worse than no script. The current gate scripts are structure checks and reminders. After TASK-1.1.4, the local session extends them with contract-diff checks.

## 15. Stage 0 success condition

Stage 0 is successful if a local reviewer can unzip the package, inspect the tree, verify that the contracts are marked draft, confirm that private and legacy boundaries are clear, and issue GPT-A a single unambiguous TASK-1.1.4 card. It is not successful if it encourages GPT-A to edit docs/contracts directly, implement unrelated modules, or assume a frozen contract.

## 16. What Stage 0 deliberately leaves unresolved

Stage 0 does not decide the final shape of Account Pool schema, browser profile secrets, quota estimation, IM callback implementation, or Obsidian write permissions. Those are intentionally left to later phases because they depend on real host resources: one healthy ChatGPT profile, the user's vault scan, and local review of private boundary rules. Freezing them too early would either leak private concepts into the open contract or force later implementation to fight an artificial schema.

Instead, Stage 0 creates narrow seams: `account_hint` for future routing, `source_ref_id` for provenance, `approval_level` for risk control, and `RunRecord` event vocabulary for evidence. These seams are enough for GPT-A to implement core schemas and for local reviewers to freeze a meaningful `1.0.0` without smuggling Phase 1.2/1.3 details into Phase 1.1.
