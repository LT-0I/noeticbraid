# SP-B Round-2 修订记录

date: 2026-05-06
target round: round-2 verifier
based on: ARBITRATION.md round-1
executor: codex CLI workspace-write (方法 B, 主 session 派)

## 7 项 MUST 落实

### MUST-1 HIGH — Router fail-closed
- file:line: router.py:204-214 + router.py:227-243 + router.py:267-320
- 修复要点: 移除 ALL-models fallback, 无角色/能力候选时抛 RoutingError, 并在 route_type 入口校验最小独立模型分配
- 测试新增: tests/test_router.py::test_route_high_risk_with_writer_only_pool_fails_closed

### MUST-2 HIGH — logic_reviewer 自映射 (或 fixture 对齐)
- file:line: fixtures/dual_review_prompt_cycle.json:81
- 选定方案: B
- 选定理由: frozen ModelRoute 1.2.0 selected_models[].role enum 不含 logic_reviewer, 不扩 schema/enum
- 修复要点: fixture participant_prompt_reviewer_a.role 从 logic_reviewer 对齐为 reviewer
- 测试新增: tests/test_debate_runner.py::test_run_debate_logic_reviewer_fixture_reconstruction

### MUST-3 MED — _score_model 类型注解
- file:line: router.py:194
- 修复要点: tuple[int, int, int, str] -> tuple[int, int, int, int, str]

### MUST-4 MED — CLI 位置式
- file:line: cli.py:38, docs/API_REFERENCE.md:68, README.md:17, docs/BUILD_RECORD.md:30, docs/VERIFICATION.md:11
- 修复要点: route 子命令从命名 flag 改为 positional task_card, 文档示例同步
- 测试新增: tests/test_cli.py::test_cli_route_positional_argument

### MUST-5 MED — Objection trace 字段
- file:line: schemas/debate.schema.json:223-232 + debate_runner.py:150-153 + validator.py:207-215
- 修复要点: schema 加 raised_by/addressed_by optional, normalizer 保留, validator 校验 participant_id/manual/human
- 测试新增: tests/test_debate_runner.py::test_run_debate_preserves_objection_trace_fields

### MUST-6 MED — Objection 跨轮转移
- file:line: schemas/debate.schema.json:233-237 + validator.py:217-251 + debate_runner.py:262-289 + convergence.py:72-94
- 修复要点: 加 addresses_objection_ref 引用语义, 校验 prior/status 转移, run_debate 过滤已被 accepted/rejected 终态处理的 unresolved
- 测试新增: tests/test_debate_runner.py::test_run_debate_objection_state_transition_via_addresses_ref

### MUST-7 MED — producer/reviewer distinct
- file:line: router.py:227-243 + router.py:261-264 + router.py:267-320
- 修复要点: producer_reviewer 要求 producer/coder 与 reviewer 独立, dual_review 要求两个 reviewer 独立, multi_review 要求 reviewer 与 adversary 独立
- 测试新增: tests/test_router.py::test_route_producer_reviewer_with_single_model_pool_fails

## 不修 (列入 1.x backlog)
- 6 LOW, 见 ARBITRATION.md §SHOULD

## 测试结果
- pytest: 27 passed (command: python -m pytest -q --basetemp=.tmp/pytest-tmp -o cache_dir=.tmp/pytest-cache; exit 0; pytest-cache ACL warning emitted)
- CLI smoke: PASS 4/4
  - python -m multimodel_alliance route examples/task_card_low.json
  - python -m multimodel_alliance route examples/task_card_medium.json
  - python -m multimodel_alliance route examples/task_card_disputed.json
  - python -m multimodel_alliance run-fixture multimodel_alliance/fixtures/dual_review_prompt_cycle.json --pretty

## 红线扫描
- license: clean (jsonschema MIT + pytest MIT, 无新依赖)
- frozen ModelRoute 1.2.0: 不动
- RunRecord 边界: 不写

## 版本变更
- pyproject 0.1.0 -> 0.2.0
- zip rebuild: skip (主 session 决定)
