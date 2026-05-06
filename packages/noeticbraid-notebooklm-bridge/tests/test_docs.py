from __future__ import annotations

from pathlib import Path


def test_required_docs_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        "README.md",
        "docs/REFERENCE_RESEARCH.md",
        "docs/ARCHITECTURE.md",
        "docs/API_REFERENCE.md",
        "docs/DEVELOPER_GUIDE.md",
        "docs/C2_BROWSERSESSION_CONTRACT.md",
        "docs/SELECTOR_MAINTENANCE.md",
        "docs/RUNRECORD_INTEGRATION.md",
        "docs/SECURITY_AND_COMPLIANCE.md",
        "docs/TROUBLESHOOTING.md",
        "docs/ROADMAP.md",
    ]
    missing = [path for path in required if not (root / path).is_file()]
    assert missing == []
