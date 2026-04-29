"""Source-of-truth consistency gate.

Scan all .md files for header markers like:

    <!-- Source-of-truth: <path> (commit <hash>) -->

When such a marker exists, verify that the referenced source file's current commit
hash equals <hash>. This protects against duplicated documents drifting from their
upstream source.

Phase 1.1 currently has no duplicate documents, so this gate runs as a no-op PASS.
Future phases may introduce duplicates (e.g., a per-package README mirroring a
section of the contract); this script is future-ready.

Exit code: 0 = PASS (no markers OR all markers consistent), 1 = FAIL.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MARKER_RE = re.compile(
    r"<!--\s*Source-of-truth:\s*(?P<path>[^\s]+)\s*\(commit\s+(?P<hash>[0-9a-f]{7,40})\)\s*-->",
    re.IGNORECASE,
)


def find_markers() -> list[tuple[Path, str, str]]:
    markers: list[tuple[Path, str, str]] = []
    for md in REPO_ROOT.rglob("*.md"):
        # skip vendored / archive directories
        if any(part in {"node_modules", ".git", "legacy", "private"} for part in md.parts):
            continue
        try:
            text = md.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for m in MARKER_RE.finditer(text):
            markers.append((md, m.group("path"), m.group("hash")))
    return markers


def current_blob_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() or None
    except FileNotFoundError:
        return None


def main() -> int:
    markers = find_markers()
    if not markers:
        print("source_of_truth_check: PASS (no Source-of-truth markers in repo; future-ready)")
        return 0
    failures: list[str] = []
    for md_path, source_path, declared_hash in markers:
        source = (REPO_ROOT / source_path).resolve()
        actual = current_blob_hash(source)
        if actual is None:
            failures.append(
                f"{md_path}: Source-of-truth points to {source_path} which does not exist or has no git history"
            )
            continue
        if not actual.startswith(declared_hash):
            failures.append(
                f"{md_path}: declared {declared_hash} but {source_path} HEAD is {actual[: max(len(declared_hash), 7)]}"
            )
    if failures:
        print(f"source_of_truth_check: FAIL ({len(failures)} divergence(s))")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"source_of_truth_check: PASS ({len(markers)} marker(s) consistent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
