# Stage 2 Ledger zip 一审 (Claude Opus critic)

## 总判
PASS — 0D / 0S / 2M / 3L 设计干净、契约严守、白名单合规、并发与跨平台路径都已显式覆盖；仅 2 个非阻塞中等问题与 3 个 cosmetic。

## 14 自检项判定

| # | 项 | 实际 | 证据 (file:line / SHA) |
|---|---|---|---|
| 1 | schemas/ byte-identical to main HEAD `4a3f962` | PASS | `manifest.md:88-95` 7 个 schemas/*.py SHA 全部对齐；`schemas/run_record.py` 实测 sha256 = `92ae7fb25818f081a887216ea8c0cf86de9ac90e68eb5fa61c068f410b0dca1d` (与 manifest 一致；与 noeticbraid main HEAD `4a3f962` 一致) |
| 2 | Stage 1 tests + smoke byte-identical | PASS | `manifest.md:100-108,135` test_schema_models / test_schema_contract / fixtures / conftest / test_schema_smoke 全部列为 unchanged |
| 3 | docs/contracts/** byte-identical | PASS | `manifest.md:49-60` 全部 frozen contract 资产 SHA 对齐；`docs/contracts/phase1_1_pydantic_schemas.py` 实测 sha256 = `8b8cbd9e...` 与 manifest + main HEAD 一致 |
| 4 | pyproject.toml only adds `portalocker>=2.0,<3`; version unchanged | PASS | `pyproject.toml:3` `version = "0.1.0+stage0"`；`pyproject.toml:8-11` dependencies 仅在 `pydantic>=2.6,<3.0` 后追加 `portalocker>=2.0,<3` |
| 5 | __init__.py only appends; `__version__` untouched | PASS | `noeticbraid_core/__init__.py:5` `__version__ = "1.0.0"` 保持；`__init__.py:15-19` 追加 ledger + source_index import；`__all__` 末尾追加 3 项 |
| 6 | ledger module 2 new files, full API | PASS | `ledger/__init__.py` (6 行) + `ledger/run_ledger.py` (120 行)；`run_ledger.py:62,81,97,105,57` 提供 append / iter_all / find_by_run_id / iter_since / path |
| 7 | source_index 3 new files, runtime_checkable Protocol + FileBucketSourceIndex | PASS | `source_index/__init__.py` (8 行) / `protocols.py` (27 行) / `source_index.py` (124 行)；`protocols.py:13` `@runtime_checkable` ✓ |
| 8 | Windows-safe paths: 无 `:` | PASS | `source_index.py:80-83` `_bucket_path` 用 `hex_part` (sha256: 前缀已剥离)；`test_source_index.py:61-67` 显式 assert `: not in entry.name` |
| 9 | LOCK_EX + 4 进程并发 | PASS | `run_ledger.py:72` `portalocker.lock(fh, portalocker.LOCK_EX)`；`test_ledger.py:60-71` 4 进程 × 100 records = 400 全部 unique；manifest 显示 `test_4_processes_400_records_no_corruption PASSED` |
| 10 | corrupted record warning + skip/None | PASS | `run_ledger.py:91-95` iter_all 损坏行 `LOGGER.warning + continue`；`source_index.py:100-104` get 损坏返回 None；`test_ledger.py:74-84` + `test_source_index.py:50-57` 覆盖 |
| 11 | B 不 import guard / ModeEnforcer / Decision / LedgerSink | PASS | grep 全部 ledger/ + source_index/ 无 guard 相关 import；唯一 "guard" 字面出现在 `run_ledger.py:65` 注释 "lock guards the file handle"（不是符号引用） |
| 12 | reuse_log only adds new file | PASS | `manifest.md:124,126` Stage 0 旧文件 SHA = `e8a11d96...` 列为 unchanged；新文件 `phase1_1_stage2_ledger_reuse_candidates.md` 列为 added |
| 13 | pytest 23 PASSED + contract_diff PASS + 262 PASSED | PASS | manifest 完整粘贴 23 项 ledger+source_index 测试均 PASSED；contract_diff 6 模型等价；schema-suite 262 PASSED |
| 14 | blacklist untouched + zip 命名 + sha256 sidecar | PASS | 黑名单 73 项 SHA 全部对齐；`manifest.md:9` 引用外部 `noeticbraid_phase1_1_stage2_ledger.zip.sha256` sidecar |

## 新硬伤

| 级 | 项 | 文件:行 | 说明 |
|---|---|---|---|
| M | `iter_all` / `iter_since` 读路径无 LOCK_SH 共享锁 | `run_ledger.py:81-95,105-119` | 设计上 append 用 LOCK_EX 独占锁，但 iter_all 直接 `open(..., "r")` 无锁。如果一个进程正在 append（持 EX 锁、写未完成 fsync 前），另一个进程 iter_all 可能读到部分行。Phase 1.1 内 RunLedger 单 writer 多 reader 场景下不致命；并发测试只测了多 writer，没测 writer+reader 同时。设计 v2 是否要求读路径加 LOCK_SH 是 spec 留白；标 M 而非 D，因不阻断当前用例。Fix：iter_all 入口加 `portalocker.lock(fh, portalocker.LOCK_SH)` 或 spec 明确"读非锁"。 |
| M | `iter_all` 实现是 generator，`open()` 在 yield 期间持有；调用方未消费完则文件句柄泄漏到 GC | `run_ledger.py:86-95` | `with open(...) as fh:` 内 `yield`，若调用方 `next()` 一次后丢弃 generator，句柄要等 GC 才关闭。Linux 影响小，Windows 上其它进程可能无法删除 / rename 文件。`find_by_run_id` 找到即 return 时 generator 中断 → 触发 GeneratorExit → context manager 关 fh，OK。但外部 `next(ledger.iter_all())` 后弃置就有窗口。标 M（非阻塞）。Fix：考虑一次性读完返回 list，或在文档说明"必须 close generator"。 |
| L | manifest "字数" 列单位含义不清 | `manifest.md:38` 表头 | "字数" 实际是 byte size 不是 word count；中文歧义。cosmetic。 |
| L | `run_ledger.py:93,103,119` 用 bare `Exception` 而非 `ValidationError` 等具体类型 | `run_ledger.py:93,103` `source_index.py:102,119` | 注释 `pragma: no cover - exact exception is pydantic-specific` 已说明，但严格类型派会要求 catch `ValidationError`。Phase 1.1 接受。 |
| L | reuse_log 第 23 行声明"jsonlines 已在 Stage 0 reuse_log 列"未交叉验证 | `phase1_1_stage2_ledger_reuse_candidates.md:23` | Stage 0 的 `phase1_1_reuse_candidates.md` 是否实际列了 jsonlines 我未追读；本任务 GPT-B 明示不依赖 jsonlines，所以即便 Stage 0 没列也无影响。cosmetic。 |

## 跨 prompt 一致性

| 检查项 | 判定 | 说明 |
|---|---|---|
| baseline 措辞 = main HEAD `4a3f962` 而非 tag | PASS | `manifest.md:10-19` 显式声明 `baseline_input_ref: main HEAD (commit 4a3f962)` + `baseline_input_archive_command: git archive main` + 单列 `contract_freeze_commit: 4be314d (tag pin only, NOT archive ref)`，这是 v3 prompt §二.2 "tag 仅作 contract version provenance pin" 的精确执行 |
| 写入边界白名单 11 项严格遵守 | PASS | 修改 3 (pyproject.toml + noeticbraid_core/__init__.py + manifest.md) + 新增 8 (ledger/__init__.py + run_ledger.py + source_index/__init__.py + protocols.py + source_index.py + test_ledger.py + test_source_index.py + reuse_log/phase1_1_stage2_ledger_reuse_candidates.md) = 11；零越界 |
| 黑名单字节级保留 | PASS | 抽样 5 个高风险 baseline 文件实际 SHA 与 manifest 列出的 SHA 完全一致；manifest 73 项 unchanged 列表覆盖 docs/contracts/** + schemas/** + tests/** + console/** + obsidian/** + runtime/** + scripts/** + 顶级 LICENSE/NOTICE/README/.gitignore/.editorconfig/pyproject.toml/pnpm-workspace.yaml + legacy/** + private/** |
| 不 import guard / ModeEnforcer / Decision / LedgerSink | PASS | grep 全 ledger/ + source_index/ 仅有 1 处 "guard" 出现在自然语言注释；零符号引用 |
| __version__ 不动 | PASS | `noeticbraid_core/__init__.py:5` `__version__ = "1.0.0"` 与 main HEAD 一致；GPT-B 仅追加 import 行 + __all__ 末尾 3 项 |
| version pin 用 `0.1.0+stage0` (PEP 440 local segment) | PASS | `pyproject.toml:3` `version = "0.1.0+stage0"`；v2 修订 S-1 已落地 |
| pytest 阈值 ≥ 17 PASSED | PASS | manifest 显示 23 PASSED（v2 升级线）；超过阈值 |
| `RunRecord.created_at` UTC normalize 处理 | PASS | `run_ledger.py:113-116` naive datetime → 视为 UTC；aware datetime → `astimezone(UTC)`；测试 `test_iter_since_naive_treated_as_utc` 显式覆盖 |
| `content_hash` 71 字符 + lowercase hex | PASS | `source_index.py:51-54` `_strip_prefix` 强制 lowercase + 64 hex 验证 |
| Phase 1.2 SQLite swap 路径预留 | PASS | `protocols.py:13` `@runtime_checkable` + `source_index.py:57` `class FileBucketSourceIndex(SourceIndexBackend)` 显式继承 Protocol；`source_index.py:20-23` doc 说明 SqliteSourceIndex 替换路径 |
| 跨模块解耦（B 不调 C） | PASS | append 不做权限检查；注释 `run_ledger.py:12-15` 显式说明 |
| 无 latest-pinned 依赖 | PASS | `pyproject.toml:8-11` `pydantic>=2.6,<3.0` + `portalocker>=2.0,<3` 全部 lower bound + upper bound |
| PR # 引用合规 (#TBD 或历史 #1/#2) | PASS | manifest 仅引用 `4be314d` (PR #1) + `4a3f962` (PR #2)；ledger 路本身的 PR # 不在此 zip 写入是预期的（zip 不跑 git） |
| 无 private/ leak | PASS | `private/` 仅 4 个 README 占位 SHA 与 main HEAD 一致 |

## 进 GPT-A 的判断

PASS — ledger zip 设计干净、契约严守、所有 14 项自检证据可独立验证；2 个 M 级问题（reader 无锁 / generator 句柄）属 Phase 1.1 接受的非阻塞设计权衡，可在 Stage 3 集成或 Phase 1.2 升级时再收紧。建议本地主 session 直接进入 Codex 二审；若 Codex 也 PASS，可解压到 stage2/ledger 分支开 PR。
