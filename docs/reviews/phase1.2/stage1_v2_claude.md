# Phase 1.2 Stage 1 v2 Confirmation Review (Critic)

## Per-dimension verdicts

| # | Group | Dim | Verdict | Note | Fix if not PASS |
|---|---|---|---|---|---|
| 1 | A | OpenAPI 13 schemas runtime | PASS | Main session实测 `set(ALL_SCHEMA_NAMES) ⊆ components.schemas.keys()` 0 missing 0 extra；本审查也 byte 验证 v2_merged/app.py 确实 install 了 `app.openapi = lambda: _build_custom_openapi(app)` 且 `_build_custom_openapi` 正确遍历 `CORE_SCHEMA_MODELS` 注入 schemas | — |
| 2 | A | _build_custom_openapi 实现 | PASS | `app.py:31-52` 顺序正确：先 cache hit-return，后 `get_openapi(...)`，再 `setdefault("components",{}).setdefault("schemas",{})` 不覆盖已有 schema，最后写回 `app.openapi_schema`。`setdefault` 双层链确保 wrapper schemas 不被 core schemas 覆盖。`ref_template="#/components/schemas/{model}"` 与 FastAPI 默认 ref 模板一致 | — |
| 3 | A | CORE_SCHEMA_MODELS 元组 | PASS | `contracts.py:147-154` 6 模型与 `ALL_SCHEMA_NAMES` 末 6 项 (Task, RunRecord, SourceRecord, ApprovalRequest, SideNote, DigestionItem) 顺序完全对齐。`__all__` 也已 export | — |
| 4 | A | 新测试有效性 | PASS | `test_app_contract_routes.py:84-95` 同时校验 (a) `set(ALL_SCHEMA_NAMES) ⊆ components.keys()` (b) 7 wrapper schemas 各自 properties 字段名。每测试独立 `_client(tmp_path)` 构建新 app，无 cross-test 污染 | — |
| 5 | A | shared_changes.md item 6 | PASS | 与 v1 diff 仅追加 item 6 (5 行)；items 1-5 byte-equal。文字内容描述准确（current state + license 状态 + 集中管理建议 + 本阶段不强制） | — |
| 6 | B | v2 zip scope | PASS | v2_extracted 仅 5 文件（manifest + shared_changes + 3 backend）；无 core/console/contracts/root paths | — |
| 7 | B | 7 routes byte-equal | PASS | account/approval/auth/dashboard/health/ledger/workspace 7 个 routes/*.py 在 v1_extracted vs v2_merged SHA256 完全一致 | — |
| 8 | B | DPAPI/token/vault byte-equal | PASS | `auth/{dpapi,token_store,vault}.py` SHA256 v1=v2 | — |
| 9 | B | settings/storage byte-equal | PASS | `settings.py`, `storage/__init__.py`, `storage/factories.py` SHA256 v1=v2 | — |
| 10 | B | pyproject.toml byte-equal | PASS | `packages/noeticbraid-backend/pyproject.toml` v1 SHA = v2 SHA = `d2e005132ae7e884decf685a20a088ec13fc9491950aa7af5a68e0f2a789c6f7`；runtime deps 仍 fastapi/pydantic/noeticbraid-core | — |
| 11 | C | OpenAPI 副作用 | PASS | (a) lifespan 顺序：`_validate_core_imports` 在 lifespan 内执行；`_build_custom_openapi` 不依赖 `app.state.core_import_ok`，二者独立。(b) cache 隔离：`app.openapi_schema` per-instance；每个测试用 `_client(tmp_path)` 创建独立 app，无跨测试污染。(c) FastAPI 兼容：用 `fastapi.openapi.utils.get_openapi` 是官方推荐 customization API（FastAPI docs "Extending OpenAPI"）；非 monkey-patch 内部 `_openapi_kwargs`。(d) `setdefault` 不覆盖 wrapper schemas，安全 | — |
| 12 | C | _FallbackCoreModel 影响 | MINOR | 在生产 (core 可装) 路径，6 个 schemas 含真字段；在 sandbox (core 不可用) 路径，fallback 仅声明 `pass`，`model_json_schema()` 输出 `{"properties": {}, "additionalProperties": false, ...}`。Lane C SDK generator（如 openapi-generator）拿空 properties 会生成空 class — 不破坏 SDK pipeline，但生成的类型对调用方无字段，是仅 sandbox 场景的退化 | 建议：在 manifest.md 或 shared_changes.md 加 1 行文字 caveat：「Lane C SDK gen 必须以 core 已安装的环境运行；sandbox-only 路径产出的 SDK 类对 6 core schemas 字段为空」。本阶段非阻塞；移到 Stage 2A 前的主 session 决策即可 |

## v2 是否解决 v1 MAJOR/MINOR

- MAJOR (13 schemas): SOLVED  
  Evidence: 主 session `/openapi.json` 13 keys 完美匹配 + 本审查 diff 验证 `_build_custom_openapi` 正确实现。
- MINOR (test gate): SOLVED  
  Evidence: `test_openapi_components_contain_all_thirteen_schemas` 双层断言（13 names subset + 7 wrapper field 字段）。
- MINOR (dev deps): SOLVED  
  Evidence: shared_changes.md item 6 完全按 v2 prompt 要求追加，未触碰 backend pyproject.toml（仍 byte-equal）。

## v2 是否引入新问题

1 个 MINOR 风险（dim 12）：sandbox 路径下 `_FallbackCoreModel` 空字段对 Lane C SDK gen 的语义退化。非 v2 patch 引入（v1 已存在 fallback），但 v2 把 fallback 显式注入 `components.schemas` 后才暴露此面。**非阻塞**：生产路径 core 总在；本阶段验证目标是 contract 层路由 + schema 注册，非 SDK 字段验证。

## 总裁决

PROCEED

理由：v2 patch 三项必修全部 SOLVED，主 session 实测 + 本审查 diff/SHA byte-equal 双层证据完整。v1 23 文件 byte-equal carry-forward 100% 确认（含 7 routes、auth 三件套、settings、pyproject）。`_build_custom_openapi` 实现严格遵循 FastAPI 官方 customization 模式，cache + per-instance 测试隔离均无副作用。dim 12 sandbox SDK gen 字段空退化是 v1 已存在的 fallback 设计后果，仅在 sandbox 路径触发，记入 Stage 2A 主 session 决策即可。无需再次 REVISE_GPT_A。
