from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "pyproject.toml",
    "pnpm-workspace.yaml",
    "packages/noeticbraid-core/pyproject.toml",
    "packages/noeticbraid-console/package.json",
    "packages/noeticbraid-obsidian/pyproject.toml",
    "packages/noeticbraid-runtime/pyproject.toml",
    "docs/contracts/phase1_1_api_contract.md",
    "docs/contracts/phase1_1_pydantic_schemas.py",
    "docs/contracts/phase1_1_openapi.yaml",
    "reuse_log/phase1_1_reuse_candidates.md",
    "legacy/helixmind_phase1/.legacy_readonly_marker",
]


def main() -> int:
    rows = []
    ok = True
    for rel in REQUIRED:
        exists = (ROOT / rel).exists()
        rows.append((rel, "PASS" if exists else "FAIL"))
        ok = ok and exists
    print("Gate 1.0 -> 1.1")
    for rel, status in rows:
        print(f"{status:4}  {rel}")
    # TODO: schema 1.0.0 freeze checks are added by local owner after TASK-1.1.4.
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
