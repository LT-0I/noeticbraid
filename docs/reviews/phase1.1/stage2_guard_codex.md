I could not write `C:/Users/13080/Desktop/HBA/GPT5_Workflow/.tmp/stage2_zip_reviews/guard_review_codex.md`: the sandbox is read-only and rejected the patch. Report body follows.

# Stage 2 Guard zip 一审 (Codex GPT-5.5 xhigh)

## 总判
PASS — 0D / 0S / 0M / 4L

实现主体与 v3 prompt 锁定范围一致：16 actions、3 modes、48 cells、3 条 RED LINE、LedgerSink 解耦、CliRunnerRegistry echo 初始项均命中。Codex 当前沙箱禁止执行 `python`/`pytest`，所以本审不声称 fresh pytest；可读到的本地日志为 358 个 package tests 通过，另有 top-level smoke 2 tests，与 manifest 的 360 计数可闭合。

## 14 自检项判定

| # | 项 | 实际 | 证据（行号 or SHA） |
|---|---|---|---|
| 1 | 16 actions 全覆盖 | PASS；v3 要求 `Action(str, Enum)`，不是 `ActionType` | prompt:217-238；`actions.py:8-39`；`test_guard_mode_enforcer.py:133-151` |
| 2 | 3 modes | PASS；v3 为 `Mode = Literal["dry_run", "supervised", "autonomous"]`，不是 runtime Enum | prompt:253；`mode_enforcer.py:48,174-175` |
| 3 | 16×3 决策矩阵 | PASS | prompt:223-238；`mode_enforcer.py:56-140`；tests `42-107` |
| 4 | 3 RED actions 永远 deny | PASS | `mode_enforcer.py:97-101,128-139,143-149`；tests `157-189` |
| 5 | action 10 vs 12 边界 | PASS；v3 是 LLM CLI vs non-LLM subprocess；“sidenote create-new”不在 v3 表内 | prompt:232,234；`mode_enforcer.py:16-20`；test `195-210` |
| 6 | LedgerSink Protocol + no B import | PASS | `protocols.py:11-24,27-34`；guard grep ledger/source_index = 0 |
| 7 | `_NoOpLedgerSink` default | PASS | `mode_enforcer.py:170-178`；`protocols.py:27-34` |
| 8 | CliRunnerRegistry | PASS to v3: registers/looks up `CliRunnerSpec`; no separate `CliRunner Protocol` in v3 | prompt:372-405；`cli_runner_registry.py:11-67` |
| 9 | approval_timeout | PASS | `mode_enforcer.py:51-52,183-197,290-297` |
| 10 | no ledger/source_index import | PASS | `rg` over `guard/` returned 0 matches |
| 11 | core `__init__.py` only appends guard exports | PASS | preserved `1-23`; appended `25-44` |
| 12 | pyproject unchanged / no portalocker | PASS | `pyproject.toml:1-22`; manifest row `84` SHA `f1518db...` |
| 13 | Tests cover required behavior | PASS | matrix, RED, protocol, timeout, registry tests present |
| 14 | pytest verification | PASS-with-caveat | manifest `220,227-240` says 360; local log `.tmp/.../guard_pytest_local.txt:7,368` shows 358 package tests; top-level `tests/test_schema_smoke.py:13,24` supplies missing 2. Fresh Codex run blocked. |

## 新硬伤

| 级 | 项 | 文件:行 | 说明 |
|---|---|---|---|
| L | 审核清单命名与 v3 prompt 不完全一致 | prompt:932,253,372-405 | 清单写 `ActionType` / Mode Enum / `CliRunner Protocol`，但 v3 样例是 `Action`、`Mode = Literal[...]`、`CliRunnerSpec`。实现跟 v3 一致。 |
| L | fresh pytest 未由 Codex 本轮执行 | n/a | 当前沙箱拒绝 `python` / `pytest`。 |
| L | 本地 pytest 日志不是完整 manifest 命令逐字证据 | `guard_pytest_local.txt:7,368` | 日志显示 358 package tests；完整命令还应包含 top-level `tests/` 的 2 个 smoke tests。 |
| L | 当前 extracted 工作树含 `__pycache__` | `rg --files` output | 用户已预验 zip diff 未包含这些文件；应是本地 pytest 生成物。不要从当前 extracted 目录直接重打包。 |

## 16 actions / 3 modes / 48 cells 完整性

PASS。v3 表在 prompt `223-238` 锁定 16×3 verdict；实现 `_DECISION_MATRIX` 在 `mode_enforcer.py:56-140` 精确覆盖。重点 spot-check：action 9/15/16 三 mode 全 DENY；action 10 autonomous = ALLOW；action 12 autonomous = REQUIRE_APPROVAL 且先经 runner registry 检查。

## 跨 prompt 一致性

无 v3 规格漂移。需要注意的是，本轮用户清单里“action 10 vs 12 = sidenote create-new vs other”与 v3 prompt 不一致；v3 唯一 SideNote action 是 action 15 `rewrite_sidenote_existing`，且为 RED LINE 永远 DENY。action 10/12 在 v3 中明确是 `invoke_llm_code_cli` vs `invoke_subprocess`。

## 进 GPT-A 的判断
PASS — 不需要 GPT-A 出 v2；进入集成前由本地主会话跑精确 `pytest packages/noeticbraid-core/tests/ tests/ -v` 以及 contract/source-of-truth gates。