# Stage 2 Guard zip 一审 (Claude Opus critic)

## 总判
PASS — 0D / 0S / 0M / 4L 实装严丝合缝；spec §2.2.1-2.2.9 逐项命中；唯一 caveat 是 manifest 已坦白的 pydantic-v2 shim（容器 1.10.15），需本地真环境复测。

## 14 自检项判定

| # | 项 | 实际 | 证据 (file:line / SHA) |
|---|---|---|---|
| 1 | 16 actions Enum 等值 §2.2.1 | PASS | `actions.py:16-39` 16 成员，name+value 与 v3 prompt §2.2.1 表格 1:1 等值；`test_action_values_match_locked_design` (test_guard_mode_enforcer.py:133-151) 直接断言完整列表顺序 |
| 2 | 3 modes DESIGN_NOTE 在 docstring | PASS | `mode_enforcer.py:1-33` 完整含审批轴 vs 操作平面轴 + Phase 1.1 不混合声明；`Mode = Literal["dry_run", "supervised", "autonomous"]` (`mode_enforcer.py:48`)；`test_invalid_mode_raises` 显式拒 `"execution"` |
| 3 | 16×3 决策矩阵 verdict 等值 §2.2.1 | PASS | `mode_enforcer.py:56-140` `_DECISION_MATRIX` 字典 16 key × 3 mode 全覆盖；逐 cell 与 §2.2.1 表格等值；`EXPECTED` (test_guard_mode_enforcer.py:42-107) 是同一表格的独立第二份编码 |
| 4 | 3 RED actions 永远 deny | PASS | `mode_enforcer.py:97-101 / 128-132 / 134-139` action 9/15/16 三 mode 全 DENY；`RED_LINE_ACTIONS` frozenset (`mode_enforcer.py:143-149`)；`test_red_line_action_{9,15,16}_always_deny` 三 mode parametrize；reason 含 "red line" |
| 5 | action 10/12 边界规则文档化 | PASS | `mode_enforcer.py:16-20` 边界说明（CLI-LLM vs 非 LLM shell + caller 必须双 check）；`test_action_10_vs_12_disambiguation` (test_guard_mode_enforcer.py:195-210) 验证 `both_pass` 逻辑 |
| 6 | LedgerSink Protocol 在 guard/，无 ledger import | PASS | `protocols.py:11-24` `Protocol + @runtime_checkable`，`append(record: RunRecord) -> None` 签名固定；`_NoOpLedgerSink` 在同文件不继承；guard/ 全目录 grep `noeticbraid_core.ledger` = 0 匹配 |
| 7 | CliRunnerRegistry 初始 echo + 校验 | PASS | `cli_runner_registry.py:36-46` 构造时 register echo（command=["echo"], timeout=5, stdin_allowed=False）；`register` 拒空名 (49-50) / 重名 (51-52) / 0 timeout (53-56) / 空 command (57-60)；7 个 registry 测试覆盖 |
| 8 | approval_timeout 86400 + env override | PASS | `mode_enforcer.py:51-52` `APPROVAL_TIMEOUT_DEFAULT_SEC = 86400` + `APPROVAL_TIMEOUT_ENV_VAR = "NOETICBRAID_APPROVAL_TIMEOUT_SEC"`；`_resolve_timeout` 优先级 explicit > env > default (183-197)；测试 4 场景 + 非正值拒收 + timeout decision shape |
| 9 | 测试覆盖 48 cells + RED + protocol + timeout + registry | PASS | `test_guard_mode_enforcer.py` 28 个测试函数（含 48 parametrize cells + 9 RED parametrize cases + 4 timeout 场景 + 5 Decision 不变量 + with_mode + InvalidContext）；`test_cli_runner_registry.py` 13 个测试 |
| 10 | frozen 资产 SHA256 == main HEAD 4a3f962 | PASS | 抽 5 文件验：`pyproject.toml` f1518db... ✓ / `phase1_1_pydantic_schemas.py` 8b8cbd9e... ✓ / `phase1_1_api_contract.md` 2b777ba9... ✓ / `schemas/run_record.py` 92ae7fb2... ✓ / `audit_trail.md` 33b21f95... ✓；全部与 manifest 声明吻合 |
| 11 | __init__.py 仅追加 guard exports | PASS | `noeticbraid_core/__init__.py:1-23` 字节级保留 main HEAD prefix（docstring + `__version__ = "1.0.0"` + schemas import block + 原 `__all__`）；25-44 行新增 guard import + `__all__ +=` 追加 7 项 |
| 12 | reuse_log stdlib only + 不动 pyproject | PASS | `phase1_1_stage2_guard_reuse_candidates.md` 显式枚举 stdlib（dataclasses/enum/typing/os/uuid/unittest.mock）+ pytest；明写 "GPT-C does NOT modify pyproject.toml"；rejected 列含 portalocker/anyio/typing_extensions |
| 13 | manifest 自洽 + 写入边界严格 | PASS | manifest 声明 102 files = 92 main HEAD carried + 10 added；91 unchanged + 1 modified (`__init__.py`) + 10 new = 102 与 §〇.1 5 类边界一致；无越权路径 |
| 14 | pytest 全跑 PASS | PASS-with-caveat | manifest 末尾贴 `360 passed in 0.37s`；但 line 230 自陈：容器 pydantic 1.10.15 vs 项目 `>=2.6`，用了**外部** pydantic-v2 shim + `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`；shim 在 artifact 外，需本地真环境复测 |

## 新硬伤

| 级 | 项 | 文件:行 | 说明 |
|---|---|---|---|
| L | 字数列偏差 | manifest.md:88-92, 109-110 | 实测 wc -w：mode_enforcer.py=976（claim 958），test_guard_mode_enforcer.py=1145（claim 1135），test_cli_runner_registry.py=302（claim 324）。差 ≤2%，文档元数据噪音；不影响实装。 |
| L | manifest 措辞 "subprocess runner checks" 易误读 | manifest.md:109 | test_cli_runner_registry.py 实际**不跑** subprocess（无 `subprocess.run` / `Popen`）；只 unit test ModeEnforcer.check(action 12) 走 registry 分支。"subprocess runner checks" 字面易被误解为真 subprocess 执行；建议改 "registry tests + invoke_subprocess decision-path checks"。 |
| L | check() 接受 `Action \| str` 是 spec 外扩展 | mode_enforcer.py:215, 300-306 | spec §3.3.2 签名是 `check(action: Action, ...)`；实装放宽为 `Action \| str` 并通过 `_coerce_action` 把字符串解析为 Action，无效则抛 `UnknownActionError`。功能上是超集且 `test_action_string_value_is_accepted_for_registered_action` 显式覆盖；但与 spec 形状有偏离，建议在 docstring 写明扩展或回缩。 |
| L | `approval_timed_out` context 短路是 spec 外便利 | mode_enforcer.py:238-239, 290-297 | spec §2.2.6 说 "真等待逻辑 Phase 1.2 加（由 caller 实现）"；实装提前给出 `approval_timeout_decision()` 静态方法 + context flag 短路。faithful 解读 spec 的 "convenience" 意图，且测试覆盖；不破坏契约但属轻度提前实装。 |

## 16 actions × 3 modes × 48 cells 完整性

逐 cell 双向验证（`_DECISION_MATRIX` ↔ §2.2.1 ↔ test EXPECTED）三方等值，无任何 cell 缺失/多余/错值。

RED LINE 漏洞：**0**。
- action 9 `write_user_raw_vault`：dry_run=DENY / supervised=DENY / autonomous=DENY ✓
- action 15 `rewrite_sidenote_existing`：dry_run=DENY / supervised=DENY / autonomous=DENY ✓
- action 16 `cross_account_transfer`：dry_run=DENY / supervised=DENY / autonomous=DENY ✓
- 三者由 `RED_LINE_ACTIONS` frozenset 显式枚举 + `assert verdict == DENY` invariant + 红线分支 reason 含 "red line" 三重防护 (mode_enforcer.py:253-259)。

action 10 vs action 12 在 autonomous 不同：action 10 = ALLOW（mode_enforcer.py:103-107），action 12 = REQUIRE_APPROVAL（113-117）。`test_action_10_vs_12_disambiguation` 显式断言 d10.ALLOW + d12.REQUIRE_APPROVAL 后 `both_pass = False`。

## 跨 prompt 一致性

| 检查项 | 判定 | 说明 |
|---|---|---|
| §2.2.1 表 vs 实装矩阵 | PASS | 16 行 × 3 列逐 cell 1:1 等值 |
| §2.2.2 action 10/12 边界 docstring | PASS | mode_enforcer.py:16-20 引用准确 |
| §2.2.3 mode 命名 + DESIGN_NOTE | PASS | `Literal["dry_run","supervised","autonomous"]`；docstring 含 v3 prompt 要求的全部要点 |
| §2.2.4 Decision frozen + verdict Enum + reason 非空 + approval_id 一致性 | PASS | `decisions.py:18-47` `__post_init__` 四重校验（含 spec 没强制的 verdict-type 与 approval_id-type 检查，是收紧不是漂移）|
| §2.2.5 LedgerSink Protocol + _NoOpLedgerSink + 不 import ledger | PASS | protocols.py 完整满足；guard/ 内 grep ledger = 0 |
| §2.2.6 approval_timeout 86400 + env var 名 + 优先级 | PASS | mode_enforcer.py:51-52, 183-197 完整满足；非正值 explicit 抛 ValueError 是合理收紧 |
| §2.2.7 CliRunnerRegistry 初始 echo + register 校验 + lookup Optional + list_allowed sorted | PASS | cli_runner_registry.py 完整；spec 没要求 list_allowed 排序但实装排序是确定性收益 |
| §2.2.8 errors.py 4 异常类 | PASS | GuardError/UnknownActionError/InvalidContextError/CliRunnerRegistryError 全在 |
| §2.2.9 __init__.py 共享编辑边界 | PASS | 仅追加；schemas exports 6 名按原顺序保留；不预设 ledger exports；__version__ 不动 |
| §〇.1 写入白名单（5 类）| PASS | 实际增量正好命中：guard/** + 2 tests + reuse_log + manifest + __init__.py 修改 |
| §〇.2 禁写黑名单 | PASS | docs/contracts/** + schemas/** + ledger/** + source_index/** + console/** + pyproject.toml + Stage 1 既有测试 + Stage 1.5 freeze 产物 + 顶级配置 全 SHA 等值或未触动 |
| baseline = main HEAD 4a3f962（非 tag commit 4be314d）| PASS | manifest 反复声明且 SHA 抽样匹配 |

## 进 GPT-A 的判断

PASS — 实装与 v3 prompt 字字命中，0D/0S/0M，仅 4L 元数据噪音/spec 外便利扩展；本地真环境跑 pytest（含 contract_diff + check_source_of_truth_consistency）后即可进 stage2/guard 分支。
