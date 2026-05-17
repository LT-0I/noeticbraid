# SPDX-License-Identifier: Apache-2.0
"""Offline deterministic SDD-D17 deliverable materialization."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from noeticbraid_backend.platform.artifacts.ledger import _artifact_events
from noeticbraid_backend.platform.deliverable.plan import (
    _FILENAMES,
    _MATERIALIZATION_SIDECAR,
    _MATERIALIZATION_TASK_ID,
    _SOURCE_MARKDOWN_SHA256,
    Modality,
)
from noeticbraid_backend.platform.tasks import store as task_store
from noeticbraid_backend.platform.tasks.models import account_ref_for
from noeticbraid_backend.platform.workspace_paths import resolve_user_path

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)
_SLIDE_RE = re.compile(r"^\s*(\d{1,2})\.\s+(.+?)\s*$")


class MaterializationError(Exception):
    """Raised when local deterministic conversion cannot proceed honestly."""


@dataclass(frozen=True, slots=True)
class LedgerArtifact:
    modality: Modality
    task_id: str
    rel_path: str
    path: Path
    sha256: str
    bytes: int


@dataclass(frozen=True, slots=True)
class MaterializedArtifact:
    modality: Modality
    path: Path
    sha256: str
    bytes: int


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account", required=True, help="Platform account id to materialize for")


def run(args: argparse.Namespace) -> int:
    result = materialize_deliverable(str(args.account))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def materialize_deliverable(account: str) -> dict[str, Any]:
    """Render the locked slides/poster markdown into local binary deliverables."""

    slides_source = resolve_ledger_artifact(account, "slides")
    poster_source = resolve_ledger_artifact(account, "poster")
    slides_bytes = _render_pptx(slides_source.path.read_text(encoding="utf-8"))
    poster_bytes = _render_poster_png(poster_source.path.read_text(encoding="utf-8"))

    slides_path = materialized_path(account, "slides")
    poster_path = materialized_path(account, "poster")
    _atomic_write_bytes(slides_path, slides_bytes)
    _atomic_write_bytes(poster_path, poster_bytes)

    slides_record = _file_record(slides_path)
    poster_record = _file_record(poster_path)
    existing = read_sidecar(account)
    materialized_at = _stable_materialized_at(existing)
    sidecar = {
        "materialized_at": materialized_at,
        "slides": slides_record,
        "poster": poster_record,
    }
    _atomic_write_json(sidecar_path(account), sidecar)
    return sidecar


def read_sidecar(account: str) -> dict[str, Any] | None:
    path = sidecar_path(account)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def sidecar_path(account: str) -> Path:
    return resolve_user_path(
        account,
        f"tasks/{_MATERIALIZATION_TASK_ID}/artifacts/{_MATERIALIZATION_SIDECAR}",
    )


def materialized_path(account: str, modality: Modality) -> Path:
    if modality not in {"slides", "poster"}:
        raise MaterializationError(f"unsupported materialized modality: {modality}")
    return resolve_user_path(
        account,
        f"tasks/{_MATERIALIZATION_TASK_ID}/artifacts/{_FILENAMES[modality][1]}",
    )


def resolve_ledger_artifact(account: str, modality: Modality) -> LedgerArtifact:
    if modality not in _SOURCE_MARKDOWN_SHA256 and modality != "document":
        raise MaterializationError(f"unsupported ledger modality: {modality}")
    task_id = _MATERIALIZATION_TASK_ID if modality in {"slides", "poster"} else "task_promo_smoke_1778967211"
    _load_owned_task(account, task_id)
    events = _artifact_events(account, task_id)
    expected_sha = _SOURCE_MARKDOWN_SHA256.get(modality)
    fallback: LedgerArtifact | None = None
    for payload in events:
        if str(payload.get("modality") or "") != modality:
            continue
        sha256 = str(payload.get("sha256") or "").lower()
        rel_path = str(payload.get("rel_path") or "")
        path = resolve_user_path(account, rel_path)
        if not path.is_file():
            continue
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha != sha256:
            continue
        bytes_count = int(payload.get("bytes") or 0)
        if path.stat().st_size != bytes_count:
            continue
        candidate = LedgerArtifact(
            modality=modality,
            task_id=task_id,
            rel_path=rel_path,
            path=path,
            sha256=sha256,
            bytes=bytes_count,
        )
        if expected_sha is None or sha256 == expected_sha:
            return candidate
        if fallback is None:
            fallback = candidate
    if fallback is not None:
        return fallback
    raise MaterializationError(f"ledgered source artifact not found for {modality}")


def resolve_materialized_artifact(account: str, modality: Modality) -> MaterializedArtifact | None:
    if modality not in {"slides", "poster"}:
        return None
    sidecar = read_sidecar(account)
    if sidecar is None:
        return None
    record = sidecar.get(modality)
    if not isinstance(record, dict):
        return None
    expected_sha = record.get("sha256")
    expected_bytes = record.get("bytes")
    if not isinstance(expected_sha, str) or not isinstance(expected_bytes, int):
        return None
    path = materialized_path(account, modality)
    if not path.is_file():
        return None
    data = path.read_bytes()
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != expected_sha.lower() or len(data) != expected_bytes:
        return None
    return MaterializedArtifact(modality=modality, path=path, sha256=actual_sha, bytes=len(data))


def _load_owned_task(account: str, task_id: str) -> None:
    task = task_store.load_task(account, task_id)
    if task.account_id_ref != account_ref_for(account):
        raise MaterializationError("task/account binding mismatch")


def _stable_materialized_at(existing: dict[str, Any] | None) -> str:
    if existing is not None:
        value = existing.get("materialized_at")
        if isinstance(value, str) and value:
            return value
    return datetime.now(UTC).isoformat()


def _file_record(path: Path) -> dict[str, int | str]:
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        os.replace(temp_path, path)
        temp_name = None
        path.chmod(0o600)
    finally:
        if temp_name is not None:
            try:
                Path(temp_name).unlink()
            except OSError:
                pass


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8") + b"\n"
    json.loads(encoded.decode("utf-8"))
    _atomic_write_bytes(path, encoded)


def _render_pptx(markdown: str) -> bytes:
    slides = _parse_slide_markdown(markdown)
    entries: list[tuple[str, bytes]] = [
        ("[Content_Types].xml", _content_types_xml(len(slides)).encode("utf-8")),
        ("_rels/.rels", _package_rels_xml().encode("utf-8")),
        ("docProps/app.xml", _app_props_xml(len(slides)).encode("utf-8")),
        ("docProps/core.xml", _core_props_xml().encode("utf-8")),
        ("ppt/presentation.xml", _presentation_xml(len(slides)).encode("utf-8")),
        ("ppt/_rels/presentation.xml.rels", _presentation_rels_xml(len(slides)).encode("utf-8")),
    ]
    for index, slide in enumerate(slides, start=1):
        entries.append((f"ppt/slides/slide{index}.xml", _slide_xml(slide[0], slide[1], index).encode("utf-8")))
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name)
            info.date_time = _ZIP_EPOCH
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, data)
    return archive.getvalue()


def _parse_slide_markdown(markdown: str) -> list[tuple[str, list[str]]]:
    slides: list[tuple[str, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _SLIDE_RE.match(line)
        if match is not None:
            if current_title is not None:
                slides.append((current_title, current_lines))
            current_title = match.group(2)
            current_lines = []
            continue
        if current_title is None:
            current_title = line.lstrip("# ")
            current_lines = []
        else:
            current_lines.append(line.lstrip("-• "))
    if current_title is not None:
        slides.append((current_title, current_lines))
    if not slides:
        slides.append(("NoeticBraid", ["Enterprise AI task panels with traceable execution."]))
    return slides[:24]


def _render_poster_png(markdown: str) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - guarded by environment/provisioning
        raise MaterializationError("Pillow is required for poster materialization") from exc

    width, height = 1200, 1800
    image = Image.new("RGB", (width, height), (247, 240, 228))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    accent = (146, 81, 45)
    ink = (41, 34, 28)
    muted = (93, 78, 68)
    draw.rectangle((0, 0, width, 170), fill=(238, 222, 199))
    draw.text((72, 56), "NoeticBraid", fill=accent, font=font)
    draw.text((72, 92), "Multi-User AI Workspaces for Structured, Traceable Execution", fill=ink, font=font)
    draw.line((72, 190, width - 72, 190), fill=accent, width=3)

    lines = _poster_lines(markdown)
    y = 230
    for block_index, block in enumerate(lines[:42]):
        color = accent if block_index in {0, 6, 14, 24, 34} else (ink if block_index % 6 == 0 else muted)
        for wrapped in _wrap_text(block, 120):
            draw.text((72, y), wrapped, fill=color, font=font)
            y += 25
            if y > height - 130:
                break
        y += 8
        if y > height - 130:
            break
    draw.line((72, height - 108, width - 72, height - 108), fill=accent, width=2)
    draw.text((72, height - 80), "Deterministic local poster rendering from ledgered markdown", fill=muted, font=font)
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _poster_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    skip_labels = {"poster title", "hero line", "subheadline", "core message blocks"}
    for raw in markdown.splitlines():
        line = raw.strip().strip("#")
        if not line:
            continue
        if line.lower() in skip_labels:
            continue
        if line in {"NoeticBraid"} and lines:
            continue
        lines.append(line.lstrip("-• "))
    return lines or ["NoeticBraid", "Structured, traceable enterprise AI execution."]


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}"
    lines.append(current)
    return lines


def _content_types_xml(slide_count: int) -> str:
    slide_overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        f"{slide_overrides}</Types>"
    )


def _package_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="ppt/presentation.xml"/>'
        '<Relationship Id="rId2" '
        'Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" '
        'Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _presentation_xml(slide_count: int) -> str:
    sld_ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, slide_count + 1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        f"<p:sldIdLst>{sld_ids}</p:sldIdLst>"
        '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )


def _presentation_rels_xml(slide_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{i}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{rels}</Relationships>"
    )


def _slide_xml(title: str, body_lines: list[str], index: int) -> str:
    safe_title = title[:160]
    body_paragraphs = body_lines[:10] or ["NoeticBraid promo material"]
    body_xml = "".join(_text_paragraph(line[:220], size="1800") for line in body_paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        '<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/>'
        '<p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/>'
        '<a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f'{_shape_xml(shape_id=2, name=f"Title {index}", x=685800, y=457200, cx=10820400, cy=914400, text=_text_paragraph(safe_title, size="3400", bold=True))}'
        f'{_shape_xml(shape_id=3, name=f"Body {index}", x=914400, y=1600200, cx=10210800, cy=4114800, text=body_xml)}'
        "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def _shape_xml(*, shape_id: int, name: str, x: int, y: int, cx: int, cy: int, text: str) -> str:
    return (
        "<p:sp><p:nvSpPr>"
        f'<p:cNvPr id="{shape_id}" name="{xml_escape(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/>'
        "</p:nvSpPr><p:spPr><a:xfrm>"
        f'<a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>'
        "</a:xfrm><a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom></p:spPr>"
        f"<p:txBody><a:bodyPr wrap=\"square\"/><a:lstStyle/>{text}</p:txBody></p:sp>"
    )


def _text_paragraph(text: str, *, size: str, bold: bool = False) -> str:
    bold_attr = ' b="1"' if bold else ""
    return (
        "<a:p><a:r>"
        f'<a:rPr lang="en-US" sz="{size}"{bold_attr}/>'
        f"<a:t>{xml_escape(text)}</a:t>"
        "</a:r></a:p>"
    )


def _app_props_xml(slide_count: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>NoeticBraid local materializer</Application>'
        f"<Slides>{slide_count}</Slides>"
        "</Properties>"
    )


def _core_props_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>NoeticBraid Promo Deck</dc:title>'
        '<dc:creator>NoeticBraid local materializer</dc:creator>'
        '<cp:lastModifiedBy>NoeticBraid local materializer</cp:lastModifiedBy>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:modified>'
        "</cp:coreProperties>"
    )


__all__ = [
    "LedgerArtifact",
    "MaterializationError",
    "MaterializedArtifact",
    "add_arguments",
    "materialize_deliverable",
    "materialized_path",
    "read_sidecar",
    "resolve_ledger_artifact",
    "resolve_materialized_artifact",
    "run",
    "sidecar_path",
]
