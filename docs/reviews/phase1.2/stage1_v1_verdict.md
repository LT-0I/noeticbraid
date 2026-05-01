# Phase 1.2 Stage 1 v1 双审仲裁

- 审查日期：2026-04-30
- 仲裁者：Claude Code 主 session
- 审查输入：`responses/round1_step11_phase1_2_stage1/noeticbraid_phase1_2_stage1.zip` (SHA256 `1b924032f5bbf564bd9d5b6661536e3fc8ff47146617f24a3ffc18c675b9bbd4`)
- 审查报告：
  - codex: `.tmp/phase1_2_stage1_review_codex.md`（裁决 REVISE_GPT_A）
  - critic: `.tmp/phase1_2_stage1_review_critic.md`（裁决 PROCEED with 1 MAJOR）
- 仲裁裁决：**REVISE_GPT_A**（v2 round）

## 一致性矩阵

| 维度 | codex | critic | 仲裁 |
|---|---|---|---|
| 7 paths | PASS | PASS | PASS |
| **13 schemas (#2/#6)** | **MAJOR** | **MAJOR** | **MAJOR (确认)** |
| no requestBody | PASS | PASS | PASS |
| profiles only | PASS | PASS | PASS |
| AccountProfile not introduced | PASS | PASS | PASS |
| Lane A 边界 (7-11) | 全 PASS | 全 PASS | 全 PASS |
| app factory + routes | PASS | PASS | PASS |
| DPAPI ctypes only | PASS | PASS | PASS |
| non-Win NotImplementedError | PASS | PASS | PASS |
| sqlite3 only | PASS | PASS | PASS |
| WAL + busy_timeout | PASS | MINOR (3.13 默认值容错) | PASS（Pythonpath 3.11 也设 5000ms 显式 OK） |
| CORS | PASS | PASS | PASS |
| SPDX headers | PASS | PASS | PASS |
| pyproject license | PASS | PASS | PASS |
| **dev deps (#20)** | **MAJOR** | 未列 | **MINOR (procedural)** |
| 测试通过 | PASS | PASS | PASS |
| 测试覆盖 | MINOR | PASS | MINOR |

## 最终必修清单

### MAJOR — OpenAPI 13 schemas 缺口

**问题**：
- `contracts.py:118-144` core schemas 通过 importlib try/except，fallback 为空 `_FallbackCoreModel`（无字段）
- `app.py:54-78` 用默认 `FastAPI(...)`，未自定义 `app.openapi`
- 运行时 `/openapi.json` `components.schemas` 仅含 7 个 wrapper schemas，**6 个 core schemas（Task/RunRecord/SourceRecord/ApprovalRequest/SideNote/DigestionItem）不出现**
- `test_thirteen_schema_names_are_referenced_by_contract_helpers` 仅断言 Python tuple，未校验 OpenAPI components

**实地核对（main session）**：已 Read `app.py` + `contracts.py` + `test_app_contract_routes.py`，确认 codex/critic 描述属实。

**风险**：
- Lane C SDK generator 从 `/openapi.json` 拉到的 components 缺 6 个 schemas
- Stage 1.5 contract freeze 时 byte-equal 对比 `phase1_1_openapi.yaml` 必失败
- v1.0.0 字段保护承诺等价破坏

**期望修法（任选一种）**：
1. 自定义 `app.openapi`：用 `get_openapi()` 生成默认，再把 6 个 core schemas 的 `model_json_schema()` 注入 `components.schemas`
2. 把 `noeticbraid-core>=1.0.0` 改为强依赖，删 fallback；要求 importlib 必须成功；同时强制把 6 个 core models 注册到 OpenAPI
3. 静态托管 `phase1_1_openapi.yaml`：覆盖 `app.openapi` 直接返回解析后的 yaml dict

任一种都需附加测试 `test_openapi_components_contain_all_thirteen_schemas`，断言 `set(ALL_SCHEMA_NAMES).issubset(schema["components"]["schemas"].keys())` + 字段级别一致性。

### MINOR — dev deps 集中管理

**问题**：`pyproject.toml:15-27` 在 backend 包内引入 pytest/httpx/uvicorn/pytest-cov 作为 optional/test deps。所有 license 合规（MIT/BSD），但 procedural 上：
- Stage 0 prompt 未明确禁止 dev deps
- 但 license whitelist 检查应在主 session 集中处理，避免每个 subpackage 独立扩张

**期望修法**：
- 不强制改 backend pyproject
- 在 `shared_changes.md` 加一条新提议：dev deps 是否 root 级管理（`tool.pdm.dev-dependencies`）

### MINOR — components.schemas 字段级测试

**问题**：`test_app_contract_routes.py:67-82` 仅断言 Python tuple `ALL_SCHEMA_NAMES` 字段名，未校验运行时 OpenAPI 的 `components.schemas` 真包含这 13 个 schema 名 + 字段集合是否对齐 frozen yaml。

**期望修法**：加 `test_openapi_components_contain_all_thirteen_schemas`，至少断言：
- `set(ALL_SCHEMA_NAMES) ⊆ schema["components"]["schemas"]`
- 每个 schema 的必需字段存在（与 `phase1_1_openapi.yaml` 对应 schema 字段集合做 issuperset 校验）

## 不修订项

下列均已 PASS，v2 不应改动：
- 7 routes 实现 + fixture
- POST /api/auth/startup_token 无 requestBody
- GET /api/account/pool 仅 profiles
- DPAPI ctypes-only skeleton
- token_store WAL + busy_timeout
- CORS middleware
- Lane A 边界（无 core/console/contracts/root edits）
- License Apache-2.0 + SPDX
- pyproject runtime deps 白名单（fastapi/pydantic/noeticbraid-core）

## 仲裁结论

**REVISE_GPT_A**（用户决策选项 B）

GPT-A 出 v2，**仅修**：
1. OpenAPI 13 schemas 暴露（MAJOR）
2. 加 components.schemas 字段级测试（MINOR）
3. shared_changes.md 加 dev deps procedural 条款（MINOR）

不动 v1 已 PASS 的任何代码。
