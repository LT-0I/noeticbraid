# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: E402
"""Inventory and byte-match checks for vendored reference files."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

VENDOR_ROOT = SRC_ROOT / "noeticbraid_backend" / "vendor"
EXPECTED_SHAS = {
    "claude_mem/LICENSE": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
    "claude_mem/upstream/src/core/schemas/context-pack.ts": "739be84cc2e22bf6f37360bc87b27d46bebd223dacdc99a0c38910db009492cb",
    "claude_mem/upstream/src/core/schemas/memory-item.ts": "7c94f0d4ae0b4859a7cd460d1ff7a4f6806d20df04c77348256d1b894232cbee",
    "claude_mem/upstream/src/utils/context-injection.ts": "765ffac3c29aceb265be529a5db8aa9402bcc5537d0799db7e007cf818075f2d",
    "everything_claude_code/LICENSE": "326146379f01bb137c0a5d3c54770c1aa31076705c8b88a7f6b26a460f6221b2",
    "everything_claude_code/upstream/schemas/state-store.schema.json": "52d462b4ac87ce8634529e1f3ff464292436e518a3f77b93c611e6a2bcbab89b",
    "everything_claude_code/upstream/scripts/lib/agent-compress.js": "c6dab227117eec9879211e8845f99c70ef370f37beab0c6399235e525df40865",
    "everything_claude_code/upstream/scripts/lib/cost-estimate.js": "bd8d55f092a00e35a3d7671efcf2954b6e5ec7b63b75e8f54ccf5ac1407a5929",
    "gbrain/LICENSE": "e56fbb5b3d95756f3fa1cfefa24732ec79f18ece1ad08a4e79e00df57e8b198c",
    "gbrain/upstream/src/core/eval-capture-scrub.ts": "1d11645cb40abe4fdaaadb28132d7735a3b5cc995c323dae7bad9c7579d02385",
    "gbrain/upstream/src/core/search/dedup.ts": "0b679996a7488c4b777c9539c1d1d049610e56594ebc2004b580306dda42d530",
    "gbrain/upstream/src/core/search/token-budget.ts": "c149ddff75b15897500d6a2637e258f84f018c8cfa8ce8cde0e8bc0deb946993",
    "gstack/LICENSE": "e56fbb5b3d95756f3fa1cfefa24732ec79f18ece1ad08a4e79e00df57e8b198c",
    "gstack/upstream/scripts/discover-skills.ts": "062b98f83a4cda814d360f7c9655156a48b51a5280f485493513de711232b274",
    "gstack/upstream/scripts/one-way-doors.ts": "40bb69c855d886c01051d56b1ffc349cb118fd211f4d2e21166a7649f281989c",
    "gstack/upstream/scripts/question-registry.ts": "12b40b2994e882ee1a289ec7d6b612efc02d3ae118e3454cc9c8c173e7a7866d",
    "oh_my_claudecode/LICENSE": "1d2b966f93feaa8928a57a69868388ee9016c86a341299fc5261ded44249af79",
    "oh_my_claudecode/upstream/src/planning/artifact-names.ts": "b212c24b9b98e0d536d9297dce20137f0a5b742864827b5921446075d3651b6c",
    "oh_my_claudecode/upstream/src/team/contracts.ts": "88790fc43a4d72a5f64e9b4e28873a30711e2b21c290e2df396ec31d1fd4185a",
    "oh_my_claudecode/upstream/src/verification/tier-selector.ts": "eb7adf3b1b2c97cfae17a1df5afcaf7caab5734f20d5a788c98f93752e4f3326",
    "tencentdb_agent_memory/LICENSE": "bcaf06dea1a63d27aab5633035b620e0127295583456c2a9402565ef63ecb0b0",
    "tencentdb_agent_memory/upstream/src/core/conversation/l0-recorder.ts": "bb1a0163d1d245d93039bca0b82c1d82c0eb4939c7a2a84bf410aa4b70414690",
    "tencentdb_agent_memory/upstream/src/core/store/search-utils.ts": "6288684358998c7be72aa882261074fdb68ca057691a4fc8605a2419b8e63ffe",
    "tencentdb_agent_memory/upstream/src/core/types.ts": "e0ad7bae29bab3b8d2478d0153629e8cb6b9f9b6204e753e385caec5e9d4cfd2",
}
EXPECTED_META = {
    "gstack": ("https://github.com/garrytan/gstack", "MIT"),
    "gbrain": ("https://github.com/garrytan/gbrain", "MIT"),
    "oh_my_claudecode": ("https://github.com/Yeachan-Heo/oh-my-claudecode", "MIT"),
    "claude_mem": ("https://github.com/thedotmack/claude-mem", "Apache-2.0"),
    "tencentdb_agent_memory": ("https://github.com/Tencent/TencentDB-Agent-Memory", "MIT"),
    "everything_claude_code": ("https://github.com/affaan-m/everything-claude-code", "MIT"),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_vendored_reference_files_byte_match_inspected_upstream_commit() -> None:
    for relative_path, expected_sha in EXPECTED_SHAS.items():
        path = VENDOR_ROOT / relative_path
        assert path.is_file(), relative_path
        assert _sha(path) == expected_sha


def test_vendor_metadata_declares_license_and_reference_only_execution() -> None:
    for name, (url, license_name) in EXPECTED_META.items():
        vendor_md = VENDOR_ROOT / name / "VENDOR.md"
        license_file = VENDOR_ROOT / name / "LICENSE"
        assert vendor_md.is_file()
        assert license_file.is_file()
        assert license_file.read_text(encoding="utf-8").strip()
        text = vendor_md.read_text(encoding="utf-8")
        assert url in text
        assert f"License: {license_name}" in text
        assert "TS/JS/JSON files under `upstream/` are reference only" in text
        assert "Inspected commit:" in text
