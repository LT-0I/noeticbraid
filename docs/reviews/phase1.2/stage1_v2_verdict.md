# Phase 1.2 Stage 1 v2 仲裁

- 审查日期：2026-04-30
- 审查输入：`responses/round1_step11_phase1_2_stage1/noeticbraid_phase1_2_stage1_v2.zip` (SHA256 `e35c7f4a1c282bb02537e0e82ed8727b4fb35f195f397a03179d2f3e89523cf8`)
- 审查报告：
  - codex: `.tmp/phase1_2_stage1_v2_review_codex.md`（PROCEED, 12/12 PASS）
  - critic: `.tmp/phase1_2_stage1_v2_review_critic.md`（PROCEED, 11 PASS + 1 non-blocking MINOR）
- **仲裁裁决：PROCEED**

## 主 session 实测证据

| 项 | 结果 |
|---|---|
| zip SHA256 | ✓ `e35c7f4a...` 与 `.sha256` sidecar 一致 |
| `pytest -q packages/noeticbraid-backend`（v2_merged） | `15 passed in 1.53s` |
| `/openapi.json` `components.schemas` 数量 | 13（精确） |
| 13 schema names 与 `ALL_SCHEMA_NAMES` | missing=[], extra=[] |
| v2 zip scope | 5 文件（manifest + shared_changes + 3 backend），合规 |

## 一致性矩阵

| 维度 | codex | critic | 仲裁 |
|---|---|---|---|
| OpenAPI 13 schemas | PASS | PASS | PASS（实测确认） |
| _build_custom_openapi 实现 | PASS | PASS | PASS |
| CORE_SCHEMA_MODELS | PASS | PASS | PASS |
| 新测试有效性 | PASS | PASS | PASS |
| shared_changes.md item 6 | PASS | PASS | PASS |
| v2 zip scope | PASS | PASS | PASS |
| 7 routes byte-equal | PASS | PASS | PASS |
| DPAPI/token/vault byte-equal | PASS | PASS | PASS |
| settings/storage byte-equal | PASS | PASS | PASS |
| pyproject byte-equal | PASS | PASS | PASS |
| OpenAPI 副作用 | PASS | PASS | PASS |
| _FallbackCoreModel 影响 | PASS | MINOR (non-blocking) | NOTE |

## v1 → v2 修订核对

| v1 问题 | v2 状态 | 证据 |
|---|---|---|
| MAJOR: OpenAPI 13 schemas 缺口 | **SOLVED** | 实测 components.schemas 13/13 |
| MINOR: components.schemas 测试 gate | **SOLVED** | `test_openapi_components_contain_all_thirteen_schemas` 跑通 |
| MINOR: dev deps procedural | **SOLVED** | `shared_changes.md` 追加 item 6 |

## 唯一 non-blocking note（critic dim 12）

当 `noeticbraid-core` 不可用（v2 sandbox 实测路径），`_FallbackCoreModel` 输出空 `properties: {}`。Lane C SDK generator 拿到空字段 schema 会生成空 class。

**处理建议**：
- **不**重发 GPT-A，**不**改 v2 代码
- 在 Stage 2A handoff 文档或 Lane C kickoff prompt 中加一条提醒：「Lane C SDK generation must run in an environment where `noeticbraid-core` is importable; fallback path produces empty schemas」
- 或 Stage 1.5 contract freeze 时，把 `phase1_1_openapi.yaml` 作为权威源（已在 Stage 1.5 计划内），不依赖运行时生成

## 仲裁结论

**PROCEED** — Stage 1 关闭，可进 Stage 1.5（contract freeze）。

按迁移计划，Stage 1.5 起在 codex 主 session 中进行（prep v2.1 已 PROCEED in principle）。
