# Phase 1.1 Reuse Candidates

- contract_version: 0.1.0
- status: DRAFT / pending local license review
- scope: Phase 1.1 Foundation Lock

These candidates are directions for local review. No third-party code is vendored here. Direct dependencies are capped and must be rechecked by the local Claude + Codex workflow before use.

## Candidates

```yaml
- name: pydantic
  url: https://github.com/pydantic/pydantic
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Pydantic v2 schema implementation in TASK-1.1.4 after draft freeze flow begins
  decision: 直接并入
  introduced_at_task: TASK-1.1.4
  license_status: pending_review
  notes: Compatible permissive license; Stage 0 only drafts strict stubs, no implementation.

- name: FastAPI
  url: https://github.com/fastapi/fastapi
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Local API server and OpenAPI surface for Console in later tasks
  decision: 直接并入
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Compatible permissive license; no server implementation in Stage 0.

- name: Playwright
  url: https://github.com/microsoft/playwright
  license: Apache-2.0
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Future persistent browser profile and Web AI Worker path
  decision: 直接并入
  introduced_at_task: TASK-1.1.6
  license_status: pending_review
  notes: Compatible with Apache-2.0; first real use after guard/profile boundaries.

- name: pytest
  url: https://github.com/pytest-dev/pytest
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Redline and schema tests in later implementation tasks
  decision: 直接并入
  introduced_at_task: TASK-1.1.4
  license_status: pending_review
  notes: Compatible permissive license.

- name: pyfakefs
  url: https://github.com/pytest-dev/pyfakefs
  license: Apache-2.0
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: ModeEnforcer file-boundary tests in TASK-1.1.6
  decision: 直接并入
  introduced_at_task: TASK-1.1.6
  license_status: pending_review
  notes: Compatible with Apache-2.0; useful for path isolation tests.

- name: React
  url: https://github.com/facebook/react
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Console UI implementation in TASK-1.1.7
  decision: 直接并入
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Compatible permissive license.

- name: Vite
  url: https://github.com/vitejs/vite
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Console dev/build tool in TASK-1.1.7
  decision: 直接并入
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Compatible permissive license.

- name: shadcn-ui
  url: https://github.com/shadcn-ui/ui
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Approval Queue and dashboard component patterns
  decision: 参考
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Prefer reference/component pattern first; local review decides direct copying.

- name: TanStack Table
  url: https://github.com/TanStack/table
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Account Dashboard and Run Ledger table views
  decision: 直接并入
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Compatible permissive license; frontend only.

- name: Obsidian Local REST API
  url: https://github.com/coddingtonbear/obsidian-local-rest-api
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Obsidian Bridge direction and API boundary reference
  decision: 参考
  introduced_at_task: TASK-1.1.5
  license_status: pending_review
  notes: Reference only in Stage 0/1.1; direct plugin dependency not decided.

- name: jsonlines
  url: https://github.com/wbolster/jsonlines
  license: BSD-3-Clause
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: JSONL append/read helper direction for Run Ledger
  decision: 参考
  introduced_at_task: TASK-1.1.5
  license_status: pending_review
  notes: Could be avoided with stdlib; evaluate before direct dependency.

- name: LangGraph
  url: https://github.com/langchain-ai/langgraph
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: State-machine and workflow graph reference direction
  decision: 参考
  introduced_at_task: TASK-1.1.5
  license_status: pending_review
  notes: Stage 1.1 likely too early for direct dependency; use as architecture reference.

- name: ntfy
  url: https://github.com/binwiederhier/ntfy
  license: Apache-2.0
  v2_reuse_log_index: "#96 in Step 4 v2 table"
  phase1_1_usage: Low-sensitivity notification fallback direction
  decision: 隔离
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Prefer external service / adapter; do not bundle server.

- name: discord.py
  url: https://github.com/Rapptz/discord.py
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Discord IM adapter direction after primary Feishu webhook path
  decision: 隔离
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Adapter token private; not core dependency in Stage 0.

- name: larksuite-oapi-sdk-python
  url: https://github.com/larksuite/oapi-sdk-python
  license: MIT
  v2_reuse_log_index: pending_local_mapping
  phase1_1_usage: Feishu/Lark notification adapter direction
  decision: 隔离
  introduced_at_task: TASK-1.1.7
  license_status: pending_review
  notes: Private token/config; Stage 0 creates no adapter implementation.
```

## Category index

- Contracts and schemas: pydantic
- Local backend: FastAPI
- Browser execution: Playwright
- Tests and redlines: pytest, pyfakefs
- Console UI: React, Vite, shadcn-ui, TanStack Table
- Obsidian bridge: Obsidian Local REST API
- Ledger/storage helpers: jsonlines
- Workflow reference: LangGraph
- IM fallback/adapters: ntfy, discord.py, larksuite-oapi-sdk-python
