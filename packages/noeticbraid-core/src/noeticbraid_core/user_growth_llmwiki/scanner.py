"""Read-only Obsidian-style vault scanner for the user-growth mirror."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping, Optional

from noeticbraid_core.schemas._common import ensure_utc_datetime, utc_now

from .models import (
    DuplicateTopicName,
    FolderSummary,
    LinkHint,
    NoteSummary,
    OrphanCluster,
    RiskFlag,
    VaultProfile,
    normalize_relative_path,
)

FRONTMATTER_DELIMITER = "---"
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build"}


@dataclass(frozen=True)
class VaultScanConfig:
    """Conservative scanner knobs.

    Paths are relative to the vault root. Explicit zones augment frontmatter and
    fixture-style heuristics; they do not grant this module write authority.
    """

    approved_fixtures_only: bool = True
    approved_fixture_roots: tuple[str | Path, ...] = ()
    approval_marker_name: str = ".noeticbraid_fixture_approved"
    raw_user_zones: tuple[str, ...] = ()
    ai_allowed_zones: tuple[str, ...] = ()
    max_markdown_bytes: int = 1_000_000

    def approved_root_paths(self) -> tuple[Path, ...]:
        return tuple(Path(path).expanduser().resolve() for path in self.approved_fixture_roots)

    def normalized_raw_zones(self) -> tuple[str, ...]:
        return tuple(normalize_relative_path(path, directory=True) for path in self.raw_user_zones)

    def normalized_ai_zones(self) -> tuple[str, ...]:
        return tuple(normalize_relative_path(path, directory=True) for path in self.ai_allowed_zones)


@dataclass(frozen=True)
class RealVaultIntegrationBoundary:
    """Explicit contract boundary for any future real-vault scanning.

    The default scanner remains fixture-only. Future callers that need to read a
    real vault must opt into this boundary and carry an explicit user
    acknowledgement at that integration point.
    """

    user_acknowledged_contract: bool
    config: VaultScanConfig = field(default_factory=lambda: VaultScanConfig(approved_fixtures_only=False))

    def scan(self, root: Path | str, *, scanned_at: Optional[datetime] = None) -> VaultProfile:
        if not self.user_acknowledged_contract:
            raise PermissionError("real vault integration requires explicit user acknowledgement")
        config = VaultScanConfig(
            approved_fixtures_only=False,
            raw_user_zones=self.config.raw_user_zones,
            ai_allowed_zones=self.config.ai_allowed_zones,
            max_markdown_bytes=self.config.max_markdown_bytes,
        )
        return VaultScanner(config).scan(root, scanned_at=scanned_at)


class VaultScanner:
    """Build a read-only VaultProfile from a fixture or user-approved vault root."""

    def __init__(self, config: Optional[VaultScanConfig] = None) -> None:
        self.config = config or VaultScanConfig()

    def scan(self, root: Path | str, *, scanned_at: Optional[datetime] = None) -> VaultProfile:
        """Return a structural profile without moving, renaming, or writing files."""

        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError("vault root must be an existing directory")
        self._ensure_fixture_root_is_approved(root_path)
        scanned_at = ensure_utc_datetime(scanned_at or utc_now())

        folders = self._iter_folders(root_path)
        markdown_paths = self._iter_markdown_paths(root_path)
        markdown_by_folder = self._group_markdown_by_folder(root_path, markdown_paths)

        raw_zones: set[str] = set(self.config.normalized_raw_zones())
        ai_zones: set[str] = set(self.config.normalized_ai_zones())
        risk_flags: list[RiskFlag] = []
        link_hints: list[LinkHint] = []
        note_data: dict[str, dict[str, object]] = {}

        for path in markdown_paths:
            rel_path = self._relative(root_path, path)
            text, truncated = self._read_markdown(path)
            if truncated:
                risk_flags.append(
                    RiskFlag(
                        code="large_markdown_skipped",
                        path=rel_path,
                        severity="light",
                        rationale="Markdown file exceeded the scanner byte cap; only initial bytes were inspected.",
                        evidence_paths=[rel_path],
                    )
                )
            frontmatter, _body = parse_frontmatter(text)
            note_type = infer_note_type(rel_path, frontmatter)
            owner_hint = infer_owner(frontmatter, rel_path, note_type)
            zone_hint = infer_zone(rel_path, frontmatter, note_type, owner_hint, self.config)
            if zone_hint == "raw_user":
                raw_zones.add(_folder_zone(rel_path))
            elif zone_hint == "ai_allowed":
                ai_zones.add(_folder_zone(rel_path))

            note_links = extract_link_hints(rel_path, text)
            link_hints.extend(note_links)
            note_data[rel_path] = {
                "frontmatter": frontmatter,
                "note_type": note_type,
                "owner_hint": owner_hint,
                "zone_hint": zone_hint,
                "outgoing_link_count": len(note_links),
                "incoming_link_count": 0,
            }

        incoming_counts = compute_incoming_counts(note_data.keys(), link_hints)
        for rel_path, count in incoming_counts.items():
            if rel_path in note_data:
                note_data[rel_path]["incoming_link_count"] = count

        folder_summary = build_folder_summary(root_path, folders, markdown_by_folder)
        missing_indexes = build_missing_index_risks(folder_summary, risk_flags)
        duplicate_topics = build_duplicate_topic_risks(folder_summary, risk_flags)
        orphan_clusters = build_orphan_cluster_risks(markdown_by_folder, note_data, risk_flags)
        build_frontmatter_template_risks(markdown_by_folder, note_data, risk_flags)
        build_ambiguous_ai_zone_risks(folder_summary, ai_zones, risk_flags)

        note_summaries = [
            NoteSummary(
                path=rel_path,
                has_frontmatter=bool(data["frontmatter"]),
                frontmatter_keys=sorted(str(key) for key in data["frontmatter"].keys()),
                note_type=str(data["note_type"]),
                owner_hint=str(data["owner_hint"]),
                zone_hint=str(data["zone_hint"]),
                outgoing_link_count=int(data["outgoing_link_count"]),
                incoming_link_count=int(data["incoming_link_count"]),
            )
            for rel_path, data in sorted(note_data.items())
        ]
        note_type_summary = dict(sorted(Counter(note.note_type for note in note_summaries).items()))

        return VaultProfile(
            vault_root_hash=shape_hash(root_path, folders, markdown_paths),
            scanned_at=scanned_at,
            folder_summary=folder_summary,
            note_summaries=note_summaries,
            note_type_summary=note_type_summary,
            raw_user_zones=sorted(raw_zones),
            ai_allowed_zones=sorted(ai_zones),
            missing_indexes=missing_indexes,
            duplicate_topic_names=duplicate_topics,
            orphan_clusters=orphan_clusters,
            link_hints=sorted(link_hints, key=lambda link: (link.source_path, link.link_kind, link.target)),
            risk_flags=sorted(risk_flags, key=lambda flag: (flag.path, flag.code, flag.severity)),
        )

    def _iter_folders(self, root_path: Path) -> list[Path]:
        folders = [root_path]
        for path in sorted(root_path.rglob("*")):
            if path.is_dir() and not _has_skipped_part(path.relative_to(root_path).parts):
                folders.append(path)
        return folders

    def _iter_markdown_paths(self, root_path: Path) -> list[Path]:
        paths: list[Path] = []
        for path in sorted(root_path.rglob("*.md")):
            if path.is_file() and not _has_skipped_part(path.relative_to(root_path).parts):
                paths.append(path)
        return paths

    def _group_markdown_by_folder(self, root_path: Path, markdown_paths: Iterable[Path]) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = defaultdict(list)
        for path in markdown_paths:
            rel = self._relative(root_path, path)
            folder = _folder_zone(rel)
            grouped[folder].append(rel)
        return {folder: sorted(paths) for folder, paths in sorted(grouped.items())}

    def _relative(self, root_path: Path, path: Path) -> str:
        rel = path.relative_to(root_path).as_posix()
        return normalize_relative_path(rel, allow_dot=rel == ".")

    def _read_markdown(self, path: Path) -> tuple[str, bool]:
        with path.open("r", encoding="utf-8") as fh:
            text = fh.read(self.config.max_markdown_bytes + 1)
        if len(text) > self.config.max_markdown_bytes:
            return text[: self.config.max_markdown_bytes], True
        return text, False

    def _ensure_fixture_root_is_approved(self, root_path: Path) -> None:
        if not self.config.approved_fixtures_only:
            return
        resolved_root = root_path.resolve()
        for approved_root in self.config.approved_root_paths():
            if _path_is_within(resolved_root, approved_root):
                return
        marker_name = self.config.approval_marker_name.strip()
        if marker_name and (resolved_root / marker_name).is_file():
            return
        raise PermissionError("VaultScanner approved fixture mode requires an approved fixture path")


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse a small YAML-like frontmatter block only when it starts the file."""

    if not text.startswith(FRONTMATTER_DELIMITER):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return {}, text
    closing_index: Optional[int] = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == FRONTMATTER_DELIMITER:
            closing_index = index
            break
    if closing_index is None:
        return {}, text
    block = lines[1:closing_index]
    body = "\n".join(lines[closing_index + 1 :])
    return parse_simple_frontmatter(block), body


def parse_simple_frontmatter(lines: list[str]) -> dict[str, object]:
    """Dependency-free parser for the fixture/frontmatter subset used here."""

    result: dict[str, object] = {}
    current_key: Optional[str] = None
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith((" ", "\t")) and current_key and line.strip().startswith("-"):
            current = result.setdefault(current_key, [])
            if isinstance(current, list):
                current.append(_parse_scalar(line.strip()[1:].strip()))
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", key):
            current_key = None
            continue
        value_text = raw_value.strip()
        if value_text == "":
            result[key] = []
            current_key = key
        else:
            result[key] = _parse_scalar(value_text)
            current_key = key
    return result


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(part.strip()) for part in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def infer_note_type(rel_path: str, frontmatter: Mapping[str, object]) -> str:
    hm_type = str(frontmatter.get("hm_type", "")).strip().lower()
    if hm_type in {"ai_observation", "report", "digestion", "digestion_item"}:
        return "digestion" if hm_type == "digestion_item" else hm_type
    if hm_type in {"user_raw", "daily", "project", "source", "meeting", "idea", "artifact"}:
        return "unknown" if hm_type == "user_raw" else hm_type

    lower = rel_path.lower()
    name = Path(rel_path).stem.lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", name) or "/daily/" in f"/{lower}":
        return "daily"
    if "meeting" in lower or "minutes" in lower:
        return "meeting"
    if "/source" in f"/{lower}" or "/raw" in f"/{lower}" or name.startswith("source"):
        return "source"
    if "/project" in f"/{lower}" or "project" in frontmatter:
        return "project"
    if "artifact" in lower or "output" in lower:
        return "artifact"
    if "digestion" in lower:
        return "digestion"
    if "report" in lower:
        return "report"
    if "ai_observation" in lower or "ai-observation" in lower:
        return "ai_observation"
    if "idea" in lower or "ideas" in lower:
        return "idea"
    return "unknown"


def infer_owner(frontmatter: Mapping[str, object], rel_path: str, note_type: str) -> str:
    owner = str(frontmatter.get("hm_owner", "")).strip().lower()
    if owner in {"user", "noeticbraid"}:
        return owner
    if note_type in {"ai_observation", "report", "digestion"}:
        return "noeticbraid"
    if str(frontmatter.get("hm_type", "")).strip().lower() == "user_raw":
        return "user"
    if rel_path.lower().startswith(("daily/", "journal/", "projects/")):
        return "user"
    return "unknown"


def infer_zone(
    rel_path: str,
    frontmatter: Mapping[str, object],
    note_type: str,
    owner_hint: str,
    config: VaultScanConfig,
) -> str:
    folder = _folder_zone(rel_path)
    explicit_raw = config.normalized_raw_zones()
    explicit_ai = config.normalized_ai_zones()
    if _path_in_zones(folder, explicit_raw):
        return "raw_user"
    if _path_in_zones(folder, explicit_ai):
        return "ai_allowed"
    hm_type = str(frontmatter.get("hm_type", "")).strip().lower()
    if owner_hint == "noeticbraid" or hm_type in {"ai_observation", "report", "digestion_item"}:
        return "ai_allowed"
    if owner_hint == "user" or hm_type == "user_raw":
        return "raw_user"
    lower = folder.lower()
    if lower.startswith(("daily/", "journal/", "projects/")) or "/journal/" in lower:
        return "raw_user"
    if any(marker in lower for marker in ("20_ai_observations", "50_digestion", "30_reports")):
        return "ai_allowed"
    return "unknown"


def extract_link_hints(rel_path: str, text: str) -> list[LinkHint]:
    hints: list[LinkHint] = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group(1).split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            hints.append(LinkHint(source_path=rel_path, target=_markdown_target_to_path(target), link_kind="wikilink"))
    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1).split("#", 1)[0].strip()
        if target and not target.startswith(("http://", "https://", "mailto:")):
            hints.append(LinkHint(source_path=rel_path, target=_markdown_target_to_path(target), link_kind="markdown"))
    return hints


def _markdown_target_to_path(target: str) -> str:
    target = target.strip().replace("\\", "/")
    if target.endswith(".md"):
        return normalize_relative_path(target, allow_dot=False)
    return normalize_relative_path(f"{target}.md", allow_dot=False)


def compute_incoming_counts(note_paths: Iterable[str], links: Iterable[LinkHint]) -> dict[str, int]:
    note_set = set(note_paths)
    by_stem: dict[str, str] = {}
    for path in note_set:
        by_stem[Path(path).stem.lower()] = path
        by_stem[path.removesuffix(".md").lower()] = path
    counts = {path: 0 for path in note_set}
    for link in links:
        target = link.target
        resolved = target if target in note_set else by_stem.get(target.removesuffix(".md").lower())
        if resolved and resolved != link.source_path:
            counts[resolved] += 1
    return counts


def build_folder_summary(
    root_path: Path, folders: list[Path], markdown_by_folder: Mapping[str, list[str]]
) -> list[FolderSummary]:
    result: list[FolderSummary] = []
    for folder in folders:
        rel = "." if folder == root_path else folder.relative_to(root_path).as_posix()
        rel_dir = normalize_relative_path(rel, directory=rel != ".")
        md_count = len(markdown_by_folder.get(rel_dir, []))
        has_index = (folder / "_index.md").exists()
        is_empty = not any(folder.iterdir())
        depth = 0 if rel_dir == "." else len(PurePathParts(rel_dir))
        result.append(
            FolderSummary(
                path=rel_dir,
                depth=depth,
                markdown_count=md_count,
                has_index=has_index,
                is_empty=is_empty,
            )
        )
    return sorted(result, key=lambda item: item.path)


def PurePathParts(path: str) -> tuple[str, ...]:
    clean = path.rstrip("/")
    if clean == ".":
        return ()
    return tuple(part for part in clean.split("/") if part)


def build_missing_index_risks(folder_summary: list[FolderSummary], risk_flags: list[RiskFlag]) -> list[str]:
    missing: list[str] = []
    for folder in folder_summary:
        if folder.path == "." or folder.markdown_count == 0 or folder.has_index:
            continue
        index_path = f"{folder.path}_index.md"
        missing.append(index_path)
        code = "missing_project_index" if folder.path.lower().startswith("projects/") or folder.path == "Projects/" else "missing_index"
        risk_flags.append(
            RiskFlag(
                code=code,
                path=folder.path,
                severity="info",
                rationale="Folder contains Markdown notes but no _index.md navigation file.",
                evidence_paths=[folder.path],
            )
        )
    return sorted(missing)


def build_duplicate_topic_risks(
    folder_summary: list[FolderSummary], risk_flags: list[RiskFlag]
) -> list[DuplicateTopicName]:
    by_norm: dict[str, list[str]] = defaultdict(list)
    for folder in folder_summary:
        if folder.path == ".":
            continue
        name = PurePathParts(folder.path)[-1]
        norm = re.sub(r"[^a-z0-9]", "", name.lower())
        if norm:
            by_norm[norm].append(folder.path)
    duplicates: list[DuplicateTopicName] = []
    for norm, paths in sorted(by_norm.items()):
        if len(paths) < 2:
            continue
        duplicate = DuplicateTopicName(normalized_name=norm, paths=sorted(paths))
        duplicates.append(duplicate)
        risk_flags.append(
            RiskFlag(
                code="duplicate_topic_name",
                path=paths[0],
                severity="info",
                rationale="Multiple folders normalize to the same topic-looking name; review before merging concepts.",
                evidence_paths=sorted(paths),
            )
        )
    return duplicates


def build_orphan_cluster_risks(
    markdown_by_folder: Mapping[str, list[str]],
    note_data: Mapping[str, Mapping[str, object]],
    risk_flags: list[RiskFlag],
) -> list[OrphanCluster]:
    clusters: list[OrphanCluster] = []
    for folder, notes in sorted(markdown_by_folder.items()):
        weak = [
            note
            for note in notes
            if int(note_data[note]["outgoing_link_count"]) == 0 and int(note_data[note]["incoming_link_count"]) == 0
        ]
        if len(weak) < 2:
            continue
        topic = "root" if folder == "." else PurePathParts(folder)[-1]
        cluster = OrphanCluster(topic=topic, path=folder, note_count=len(weak), evidence_paths=weak)
        clusters.append(cluster)
        risk_flags.append(
            RiskFlag(
                code="orphan_cluster",
                path=folder,
                severity="light",
                rationale="Two or more notes in this folder have no detected incoming or outgoing internal links.",
                evidence_paths=weak,
            )
        )
    return clusters


def build_frontmatter_template_risks(
    markdown_by_folder: Mapping[str, list[str]],
    note_data: Mapping[str, Mapping[str, object]],
    risk_flags: list[RiskFlag],
) -> None:
    for folder, notes in sorted(markdown_by_folder.items()):
        missing = [note for note in notes if not note_data[note]["frontmatter"]]
        if len(missing) < 2:
            continue
        risk_flags.append(
            RiskFlag(
                code="missing_frontmatter_template",
                path=folder,
                severity="info",
                rationale="Multiple notes in this folder have no top-of-file frontmatter block.",
                evidence_paths=missing,
            )
        )


def build_ambiguous_ai_zone_risks(
    folder_summary: list[FolderSummary], ai_zones: set[str], risk_flags: list[RiskFlag]
) -> None:
    for folder in folder_summary:
        lower_parts = {part.lower() for part in PurePathParts(folder.path)}
        if not lower_parts.intersection({"ai", "ai_notes", "ai-notes", "ai_observations"}):
            continue
        if _path_in_zones(folder.path, ai_zones):
            continue
        risk_flags.append(
            RiskFlag(
                code="ambiguous_ai_zone",
                path=folder.path,
                severity="light",
                rationale="Folder name suggests AI material, but it is not explicitly marked as AI-allowed.",
                evidence_paths=[folder.path],
            )
        )


def shape_hash(root_path: Path, folders: list[Path], markdown_paths: list[Path]) -> str:
    h = hashlib.sha256()
    for folder in folders:
        rel = "." if folder == root_path else folder.relative_to(root_path).as_posix() + "/"
        h.update(f"dir:{rel}\n".encode("utf-8"))
    for path in markdown_paths:
        rel = path.relative_to(root_path).as_posix()
        stat = path.stat()
        h.update(f"md:{rel}:{stat.st_size}\n".encode("utf-8"))
    return "sha256:" + h.hexdigest()


def _folder_zone(rel_path: str) -> str:
    parts = rel_path.split("/")[:-1]
    if not parts:
        return "."
    return normalize_relative_path("/".join(parts), directory=True)


def _path_in_zones(path: str, zones: Iterable[str]) -> bool:
    normalized = normalize_relative_path(path, directory=path != ".")
    if normalized == ".":
        return False
    for zone in zones:
        zone_norm = normalize_relative_path(zone, directory=True)
        if normalized == zone_norm or normalized.startswith(zone_norm):
            return True
    return False


def _has_skipped_part(parts: Iterable[str]) -> bool:
    return any(part in SKIP_DIRS or part == "private" for part in parts)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
