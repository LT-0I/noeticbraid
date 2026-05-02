from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path

EXPECTED_SECTIONS = ["Summary", "Decision Log", "Open Questions", "Acceptance Criteria", "Zip Inventory"]


def test_response_zip_rule_helper_accepts_manifest_first_sorted_entries(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "manifest.md").write_text(_manifest_text([]), encoding="utf-8")
    (root / "a.txt").write_text("a", encoding="utf-8")
    (root / "b.txt").write_text("b", encoding="utf-8")
    entries = ["manifest.md", "a.txt", "b.txt"]
    inventory = []
    for name in entries[1:]:
        digest = hashlib.sha256((root / name).read_bytes()).hexdigest()
        inventory.append(f"- `{name}` sha256:{digest}")
    (root / "manifest.md").write_text(_manifest_text(inventory), encoding="utf-8")

    zip_path = tmp_path / "response.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in entries:
            zf.write(root / name, name)

    assert_response_zip_rules(zip_path)


def assert_response_zip_rules(zip_path: Path) -> None:
    assert zip_path.name == "response.zip"
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert names[0] == "manifest.md"
        assert names[1:] == sorted(names[1:])
        assert "manifest.json" not in names
        manifest = zf.read("manifest.md").decode("utf-8")
        sections = [section.strip() for section in re.findall(r"^## (.+)$", manifest, flags=re.MULTILINE)]
        assert sections == EXPECTED_SECTIONS
        for name in names[1:]:
            digest = hashlib.sha256(zf.read(name)).hexdigest()
            assert f"- `{name}` sha256:{digest}" in manifest


def _manifest_text(inventory: list[str]) -> str:
    return "\n".join(
        [
            "## Summary",
            "Fixture manifest for response zip rule helper.",
            "",
            "## Decision Log",
            "- Fixture only.",
            "",
            "## Open Questions",
            "None.",
            "",
            "## Acceptance Criteria",
            "Output:",
            "  [PASS] response zip name is response.zip",
            "",
            "## Zip Inventory",
            *inventory,
            "",
        ]
    )
