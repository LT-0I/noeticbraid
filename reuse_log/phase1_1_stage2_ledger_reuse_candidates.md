# Phase 1.1 Stage 2 Ledger Reuse Candidates (B 路)

> Stage 2 GPT-B 复用清单（Run Ledger + Source Index 实装）。
>
> Stage 0 旧文件 `reuse_log/phase1_1_reuse_candidates.md` 不动；本文件为 Stage 2
> B 路新增。
>
> 状态约定：
> - **直接并入** = 必装依赖，进入 `pyproject.toml` `dependencies`
> - **参考** = 设计参考；不进 `dependencies`
> - **stdlib** = Python 标准库；无需声明

## 直接并入

| 名称 | License | 用途 | 进入位置 |
|---|---|---|---|
| portalocker | PSF-2.0 | JSONL 跨平台文件锁（Windows / Linux / macOS） | `packages/noeticbraid-core/pyproject.toml` `dependencies` 加 `portalocker>=2.0,<3` |

## 参考（不入 dependencies）

| 名称 | License | 用途 | 备注 |
|---|---|---|---|
| jsonlines | BSD-2-Clause | JSONL 解析参考 | Stage 0 reuse_log 已列；本任务直接用 `model_dump_json` + `\n` 不依赖 jsonlines 库 |

## stdlib（无需声明）

- `multiprocessing` — 4 进程并发测试用
- `pathlib` — 文件路径操作
- `json` — JSON 序列化（实际用 Pydantic `model_dump_json`）
- `logging` — 损坏行 warning
- `os` — `os.replace` 原子写 / `os.fsync`

## 测试用（已在 Stage 0 reuse_log）

| 名称 | License | 用途 | 备注 |
|---|---|---|---|
| pyfakefs | Apache-2.0 | 文件系统 mock | Stage 0 reuse_log 已列；本任务实际用 pytest 内置 `tmp_path` fixture，不依赖 pyfakefs |
| pytest | MIT | 测试 runner | `pyproject.toml` `optional-dependencies.test` Stage 1.5 已列 |

## License compatibility note

portalocker 是 PSF-2.0（Python Software Foundation License v2，与 Apache-2.0 兼容）。
本仓 `LICENSE` = Apache-2.0；引入 portalocker 不破坏顶级 license 兼容性。
