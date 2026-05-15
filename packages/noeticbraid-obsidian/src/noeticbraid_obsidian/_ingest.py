from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from .renderer import MarkdownRenderer
from .resources import load_schema
from .settings import WritePolicySettings, default_settings
from .writer import VaultWriter, WriteResult, WritePolicyViolation


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


# ── D6-02 追加 ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IngestSummary:
    """只读入库汇总（v3.2 §4 RunRecord 证据风格）。

    written  : 实际落盘的记录数（live 模式 writer.written=True）
    skipped  : 因 create-only 已存在被跳过的记录数（on_existing="skip" 时）
    dry_run  : dry_run 预览（未落盘）的记录数
    results  : 每条记录的 WriteResult，按输入顺序；skipped 的记录无 WriteResult，不入此元组
    """

    written: int
    skipped: int
    dry_run: int
    results: tuple[WriteResult, ...]


def ingest_serialized_records(
    records: Iterable[dict[str, Any]],
    *,
    vault_root: Path | str | None = None,
    settings: WritePolicySettings | None = None,
    project: str = "default",
    on_existing: str = "skip",
) -> IngestSummary:
    """把一批 D5-serializer 产出的 SourceRecord dict 幂等地批量入库。

    NORMATIVE 行为：
    1. resolved_settings = settings or default_settings()
    2. vault_root 解析（D6-01 刻意外置的 env 解析在此收口）：
       - vault_root 非 None → root = vault_root（原样透传给 ingest_source_record，
         由其下游 path_policy 施加 R-3）
       - vault_root 为 None → root = resolved_settings.vault_root_from_env()
         （读 OBSIDIAN_HUB_VAULT_ROOT；缺失/空 → 透传 SettingsError，不重写）
       —— env 解析**只做一次**（批量起点），不每条重解析
    3. on_existing 校验：必须 ∈ {"skip","raise"}；否则 raise ValueError
       （本 SDD 唯一新增的输入校验；非红线，纯参数合法性）
    4. 顺序迭代 records（单遍消费，支持 generator/iterator；不 materialize 成 list）：
       对每条 rec 调用
         ingest_source_record(rec, vault_root=root, settings=resolved_settings,
                               body="", project=project)
       —— body 恒 ""（§非目标）；settings 透传同一个对象（dry_run/create-only 红线一致）
       - 成功 → 收集 WriteResult；按 result.written 累加 written，否则累加 dry_run
       - 抛 WritePolicyViolation（create-only 命中已存在 source_ref_id）：
           · on_existing=="skip"  → 计入 skipped，**不**收集 WriteResult，继续下一条
           · on_existing=="raise" → 原样透传 WritePolicyViolation（中断；已处理的不回滚）
       - 抛其它任何异常（jsonschema / PathPolicyError / SettingsError / ...）：
           一律**原样透传**，绝不吞、不重写、不续跑（fail-fast；保证错误可见）
    5. return IngestSummary(written, skipped, dry_run, tuple(collected_results))

    红线保证（全部由 D6-01 ingest_source_record 既有施加，本函数零新策略）：
    - R-3 §7.1：每条记录路径由 ingest_source_record → resolve_path 锁死在
      `{ns}/30_run_ledger/20_sources/{year}/{month}/`；ModeEnforcer 拒 10_user_raw/；
      _validate_id 拒 path-fragment 注入。批量不改变单条保证（逐条委托）。
    - R-4 §7.2：settings 默认 dry_run（不落盘，返回 preview 计入 dry_run）；
      non_generated_overwrite_allowed=False 硬锁 → 已存在记录必由 ingest_source_record
      raise WritePolicyViolation。on_existing="skip" **不**覆盖、**不**改写、**不**放宽该锁——
      只是不让一条已存在记录中断整批（严格更安全：跳过而非覆盖）。
    - credential 防泄漏：每条记录仍走 ingest_source_record 的 schema 校验阶段。

    vault_root 信任边界（沿用 D6-01 round-2 MINOR-2）：vault_root（或 env 解析出的 root）
    是 caller 提供的**可信 vault 根**；R-3 是「vault-相对路径」保证。本函数不证明 root
    语义身份（与 D6-01 / 既有 writer 全体一致；caller 责任）。

    Args:
        records: 已序列化的 SourceRecord dict 可迭代对象（D5 serializer 输出）。单遍消费。
        vault_root: 可信 vault 根；None → 由 settings.vault_root_from_env() 解析。
        settings: 写策略；None → default_settings()（dry_run 默认）。
        project: 透传 write_stable_record 的 project 分区，默认 "default"。
        on_existing: "skip"（默认，create-only 命中已存在则跳过计 skipped）
                     | "raise"（透传 WritePolicyViolation 中断）。

    Returns:
        IngestSummary：written / skipped / dry_run 计数 + 按输入顺序的 WriteResult 元组
        （skipped 记录不含 WriteResult）。

    Raises:
        ValueError: on_existing 不在 {"skip","raise"}。
        SettingsError: vault_root=None 且 OBSIDIAN_HUB_VAULT_ROOT 缺失/空（透传）。
        WritePolicyViolation: on_existing="raise" 且命中已存在 source_ref_id（透传）。
        jsonschema.ValidationError / PathPolicyError / ...: 任一记录非法时透传（fail-fast）。
    """
    resolved_settings = settings or default_settings()
    if vault_root is None:
        root: Path | str = resolved_settings.vault_root_from_env()
    else:
        root = vault_root
    if on_existing not in ("skip", "raise"):
        raise ValueError(f"on_existing must be 'skip' or 'raise', got {on_existing!r}")

    written = 0
    skipped = 0
    dry_run = 0
    collected: list[WriteResult] = []
    for rec in records:
        try:
            result = ingest_source_record(
                rec,
                vault_root=root,
                settings=resolved_settings,
                body="",
                project=project,
            )
        except WritePolicyViolation:
            if on_existing == "raise":
                raise
            skipped += 1
            continue
        collected.append(result)
        if result.written:
            written += 1
        else:
            dry_run += 1
    return IngestSummary(written, skipped, dry_run, tuple(collected))


# ── D6-03 追加 ──────────────────────────────────────────────────────────────


def ingest_side_note(
    record: dict[str, Any],
    *,
    vault_root: Path | str,
    settings: WritePolicySettings | None = None,
    body: str = "",
    project: str = "default",
) -> WriteResult:
    """Validate a SideNote dict via render_side_note and ingest it as a create-only record.

    结构镜像 D6-01 `ingest_source_record`，但**无 jsonschema 步**：side_note 的输入
    权威契约是 `render_side_note` 自身（§1.1 裁决；side_note.schema.json 是离 render
    路径的 1.3.0 frontmatter wrapper，与 §11.b.S 2.0.0 输入/输出均不兼容）。

    NORMATIVE 行为：
    1. rendered = MarkdownRenderer().render_side_note(record, body=body)
       —— 这是**唯一验证门**：render_side_note 对全部 §11.b.S 必填字段
          (note_id / created_at / linked_source_refs / evidence_source /
           note_type / confidence / tone_constraint / user_response_channel /
           user_response) 以 _require/_validate_enum/_require_exact_string/
          _require_all_response_channels 强制；缺失/非法/`evidence_source !=
          linked_source_refs`/tone 字面量不符/channel 缺项 → 透传 RenderError
          （不吞、不重写、不放宽——§11.b.S 红线由既有 renderer 强制）
    2. record_id = rendered.frontmatter["note_id"]
       —— 取**已验证** frontmatter（render 已 _require note_id），非原始 record
    3. date = rendered.frontmatter["created_at"][:10]
       —— 已验证 created_at；须可被 resolve_path._date_parts 的
          `^\\d{4}-\\d{2}-\\d{2}$` + date.fromisoformat 严格接受，否则
          透传 PathPolicyError（不重写）
    4. writer = VaultWriter(vault_root, settings or default_settings())
       —— 与 D6-01 同：vault_root 必传（dry_run 也需）；env 不在本函数内解析
          （caller 责任，与 D6-01 一致）
    5. return writer.write_stable_record("side_note", record_id, rendered,
                                         date=date, project=project)

    红线保证（全部由既有组件自动施加，本函数零新策略）：
    - R-3 §7.1：resolve_path("side_note", ...) 把路径**硬锁**在
      `{ns}/20_episodic_memory/20_ai_observations/side_notes/{year}/{month}/`
      （AI 观察子树，与用户原始记录子树 `20_episodic_memory/10_user_raw/` 物理分离）；
      ModeEnforcer 对任何以 `{ns}/20_episodic_memory/10_user_raw/` 开头的路径
      **无条件拒写**（不论 nb_type）；_validate_id(note_id) 以 `^[A-Za-z0-9_:-]+$`
      拒 path-fragment；_date_parts 拒非 YYYY-MM-DD。
      → AI 写旁注**永远落 20_ai_observations/side_notes/，永不触碰用户原文**。
    - R-4 §7.2：settings.default_write_mode 默认 dry_run（不落盘，返回 preview）；
      non_generated_overwrite_allowed=False 硬锁 → 已存在 note_id 二次 ingest 必
      raise WritePolicyViolation（create-only，绝不覆盖已写出的旁注）。
    - §11.b.S metadata/tone 安全：由 render_side_note 在步骤 1 强制。

    vault_root 信任边界（沿用 D6-01 round-2 MINOR-2）：vault_root 是 caller 提供的
    可信 vault 根；R-3 是「vault-相对路径」保证。本函数不证明 root 语义身份。

    Args:
        record: 一个 `render_side_note` 可接受的 §11.b.S SideNote dict（contract
                2.0.0 输入形状）。**不是** D1-02 detector 的 CandidateB1SideNote
                （形状不同，需独立序列化器——见 §非目标），**也不是** 1.3.0
                frontmatter-wrapper schema 的实例。
        vault_root: 可信 vault 根（必传；dry_run 也需）。
        settings: 写策略；None → default_settings()（dry_run 默认）。
        body: 旁注正文（透传 render_side_note 的 Decision Notes 区），默认 ""。
        project: 透传 write_stable_record 的 project 分区，默认 "default"。

    Returns:
        WriteResult：relative_path / absolute_path / written / dry_run / preview_text。

    Raises:
        RenderError: 任一 §11.b.S 必填缺失/非法（透传；唯一验证门）。
        PathPolicyError: note_id 非法 或 created_at[:10] 非 YYYY-MM-DD（透传）。
        WritePolicyViolation: note_id 已存在（create-only；透传）。
    """
    rendered = MarkdownRenderer().render_side_note(record, body=body)
    record_id = rendered.frontmatter["note_id"]
    date = rendered.frontmatter["created_at"][:10]
    writer = VaultWriter(vault_root, settings or default_settings())
    return writer.write_stable_record("side_note", record_id, rendered, date=date, project=project)
