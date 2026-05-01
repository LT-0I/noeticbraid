# Phase 1.2 Stage 1 Review (Codex independent)

## Per-dimension verdicts

| # | Group | Dim | Verdict | Note | Fix if not PASS |
|---|---|---|---|---|---|
| 1 | A | 7 paths | PASS | 7 路由、method、summary 与 v1.0.0 YAML 对齐，见 `contracts.py:15-58` 与各 route decorator。 | — |
| 2 | A | 13 schemas | MAJOR | `ALL_SCHEMA_NAMES` 只是名字清单；core fallback 在 `contracts.py:126-144` 是空 `pass`，且 `app.py` 未把 6 个 core schemas 注入 OpenAPI。 | 在 `contracts.py:118-144` 删除空 fallback 或实现精确 fallback；在 `app.py:54-78` 提供静态/自定义 OpenAPI，确保 13 schemas 与 `phase1_1_openapi.yaml:80-482` 一致。 |
| 3 | A | startup_token no body | PASS | handler `startup_token()` 无参数，见 `auth.py:13-21`；测试覆盖 OpenAPI 无 requestBody。 | — |
| 4 | A | account profiles only | PASS | `/api/account/pool` 仅返回 `AccountPoolDraft(profiles=[])`，见 `account.py:13-17`。 | — |
| 5 | A | No AccountProfile | PASS | backend 产物中未发现 `AccountProfile` 类型定义。 | — |
| 6 | A | v1.0.0 fields protected | MAJOR | 7 个 wrapper 字段基本保留，但 core fallback 空模型等价于删除 6 个 schema 的全部字段。 | 同 #2；至少修正 `contracts.py:126-144`，并增加与 `phase1_1_openapi.yaml:145-482` 的字段级对比测试。 |
| 7 | B | No core edits | PASS | 产物文件清单不含 `packages/noeticbraid-core/**`。 | — |
| 8 | B | No console edits | PASS | 产物文件清单不含 `packages/noeticbraid-console/**`。 | — |
| 9 | B | No contracts edits | PASS | 产物文件清单不含 `docs/contracts/**`。 | — |
| 10 | B | Root pyproject proposal only | PASS | 根级变更只在 `shared_changes.md:1-9` 提议，未包含根 `pyproject.toml`。 | — |
| 11 | B | New code under backend | PASS | 新 `.py` / `.toml` 均位于 `packages/noeticbraid-backend/**`。 | — |
| 12 | C | app factory/routes | PASS | `create_app()` 存在并注册 7 个 router，见 `app.py:44-78`。 | — |
| 13 | C | DPAPI ctypes only | PASS | `dpapi.py:16-19` 仅用 `ctypes`、`wintypes`、`sys`、`dataclass`。 | — |
| 14 | C | non-Windows NotImplementedError | PASS | non-Windows guard 在 `dpapi.py:54-57`，测试在 `test_dpapi_boundary.py:38-47`。 | — |
| 15 | C | sqlite3 only | PASS | token store 使用 stdlib `sqlite3`，见 `token_store.py:6`、`55-62`。 | — |
| 16 | C | WAL/busy_timeout | PASS | `PRAGMA busy_timeout=5000` 与 `journal_mode=WAL` 在 `token_store.py:60-61`。 | — |
| 17 | C | CORS | PASS | CORS middleware 注册，localhost/127.0.0.1 console origins 覆盖，见 `app.py:20-27`、`62-68`。 | — |
| 18 | D | SPDX headers | PASS | 抽查与全量搜索显示 `.py` 文件首行均有 Apache-2.0 SPDX header。 | — |
| 19 | D | pyproject license | PASS | `license = { text = "Apache-2.0" }` 在 `pyproject.toml:7`。 | — |
| 20 | D | Dependency whitelist | MAJOR | runtime deps 合规，但 `pyproject.toml:15-27` 实际加入 `pytest/httpx/uvicorn/pytest-cov/pdm-backend` 等非白名单依赖面。 | 删除或移出 `pyproject.toml:15-27` 的非白名单依赖；测试/运行工具放到 `shared_changes.md` 或主 session 统一审批。 |
| 21 | E | Test passability | PASS | manifest 称 14 passed；测试数量与结构合理，使用 `tmp_path` 隔离。 | — |
| 22 | E | Test coverage | MINOR | 覆盖 7 路由、no requestBody、DPAPI、token_store，但未验证 13 schema 组件和字段与 frozen YAML 一致。 | 在 `test_app_contract_routes.py:57-82` 增加 `components.schemas` 与 `phase1_1_openapi.yaml` 的字段级对比。 |

## Top 3 改动建议（按重要性）

1. 修复 13 schemas contract preservation：不要用空 core fallback；生成或服务的 OpenAPI 必须包含 v1.0.0 的 13 个 schemas，并字段级对齐 frozen YAML。
2. 清理 backend `pyproject.toml` 的非白名单依赖：`pytest/httpx/uvicorn/pytest-cov` 应移到主 session 统一决策，不应作为 Stage 1 artifact 直接新增。
3. 补强测试：当前测试只验证 helper 名字和 route fixture，缺少对 `components.schemas` 的真实 contract gate。

## 总体裁决

REVISE_GPT_A

理由：路由骨架、DPAPI 边界、sqlite token store、CORS 和 Lane A 边界基本合格，但 13 schemas 的 contract preservation 不够严谨，且 `pyproject.toml` 引入了非白名单依赖面。这两个是明确 Stage 1 要求，不建议直接 proceed。

## 风险列表（可选）

- HIGH：FastAPI 自动 OpenAPI 可能与 frozen v1.0.0 YAML 漂移，尤其是未引用的 6 个 core schemas。
- MEDIUM：测试未把 schema 字段级一致性作为 gate，容易让 contract drift 漏过。
- LOW：本次审查未独立复跑 `pytest`，只核查了 manifest 声明与测试源码结构。