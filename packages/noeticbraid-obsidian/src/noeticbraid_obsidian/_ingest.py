from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from .renderer import MarkdownRenderer
from .resources import load_schema
from .settings import WritePolicySettings, default_settings
from .writer import VaultWriter, WriteResult


def ingest_source_record(
    record: dict[str, Any],
    *,
    vault_root: Path | str,
    settings: WritePolicySettings | None = None,
    body: str = "",
    project: str = "default",
) -> WriteResult:
    """Validate a SourceRecord dict and ingest it into the vault as a create-only stable record.

    NORMATIVE behavior:
    1. jsonschema 校验 `record` against frozen `source_record_note.schema.json`
       （`load_schema("source_record_note")` + Draft7Validator）；不合规 → raise（透传 jsonschema 错误，不重写）
    2. record_id = record["source_ref_id"]（缺失由步骤 1 的 schema required 校验先 raise）
    3. date = record["captured_at"][:10]
       —— 必须是 `YYYY-MM-DD`；`resolve_path._date_parts` 用 `date.fromisoformat` 严格校验，
          非法格式 → 透传 PathPolicyError（不重写）
    4. rendered = MarkdownRenderer().render_source_record(record, body=body)
    5. writer = VaultWriter(vault_root, settings or default_settings())
       —— rev2 CRIT 修：`VaultWriter.__init__(vault_root: Path|str, settings=None)` 真实签名
          —— vault_root **必传**（不是 `VaultWriter(settings)`）；与既有 4 个 writer 测试
          `VaultWriter(tmp_path, ...)` 模式一致。dry_run 仍需一个 vault_root 路径但不写盘
          （既有 writer 行为，`_write` dry_run 分支只算 absolute path 不落地）。env
          `OBSIDIAN_HUB_VAULT_ROOT` **不在本函数内解析**；caller 若要用 env 自行
          `settings.vault_root_from_env()` 取 Path 再传 `vault_root=`。
    6. return writer.write_stable_record("source_record", record_id, rendered, date=date, project=project)

    红线保证（全部由既有组件自动施加，本函数不新增策略）：
    - R-3 §7.1 vault 用户原始记录神圣：`resolve_path` 把路径锁死在
      `{ns}/30_run_ledger/20_sources/{year}/{month}/`；`ModeEnforcer` 拒绝 `10_user_raw/`
      与任何 allowlist 外路径；`_validate_id(source_ref_id)` 拒绝 path-fragment 注入
    - R-4 §7.2 用户主体：`settings.default_write_mode` 默认 `dry_run`（不落盘，返回 preview）；
      `non_generated_overwrite_allowed=False` 硬锁 → 已存在的 source_ref_id 二次 ingest 必 raise
      `WritePolicyViolation`（create-only，绝不覆盖用户已见过的记录）
    - credential 防泄漏：schema 校验阶段拒绝带 token/api_key 等 query 参数的 url

    vault_root 信任边界（rev2 MINOR-2 澄清）：`vault_root` 是 **caller 提供的可信 vault 根**；
    R-3 是「vault-相对路径」保证 —— `resolve_path` 把 source_record 锁在
    `30_run_ledger/20_sources/` 子树、`ModeEnforcer` 拒 `10_user_raw/`，均相对所给 root 成立。
    本函数**不**证明 caller 传的 root 在语义上「确实是那个 vault」；恶意 caller 自定 root 指向
    自己控制的目录不属本 SDD 防御面（与既有 writer 全体一致；调用方责任）。
    """
    Draft7Validator(load_schema("source_record_note")).validate(record)
    record_id = record["source_ref_id"]
    date = record["captured_at"][:10]
    rendered = MarkdownRenderer().render_source_record(record, body=body)
    writer = VaultWriter(vault_root, settings or default_settings())
    return writer.write_stable_record("source_record", record_id, rendered, date=date, project=project)
