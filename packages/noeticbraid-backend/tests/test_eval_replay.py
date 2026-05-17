# SPDX-License-Identifier: Apache-2.0
"""CI gate for the SDD-D20 §7a deterministic eval-replay harness."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent.parent
SRC_ROOT = PACKAGE_ROOT / "src"
CORE_SRC_ROOT = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
for path in (CORE_SRC_ROOT, SRC_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

# In-repo precedent for importing a scripts/ module under pytest (the repo root
# is not on the pytest pythonpath and scripts/ is not a package): mirror
# test_stage2_4_contract_gate.py:18-23 rather than `from scripts import ...`,
# so collection is robust regardless of invocation cwd.
_HARNESS_PATH = REPO_ROOT / "scripts" / "eval_replay.py"
_SPEC = importlib.util.spec_from_file_location("eval_replay", _HARNESS_PATH)
assert _SPEC is not None and _SPEC.loader is not None
eval_replay = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = eval_replay
_SPEC.loader.exec_module(eval_replay)

# Pinned copy of the production engineering-field denylist enforced by
# platform/conversation/endpoint.py:_assert_no_engineering_keys (≈ lines
# 218-232). The harness FORBIDDEN_VIEW_KEYS must remain a SUPERSET so its
# no-engineering-keys invariant never silently weakens below production. If
# production adds a key, update this pin (and the harness set) together.
_PRODUCTION_FORBIDDEN_KEYS = frozenset(
    {
        "ledger",
        "dispatch",
        "critique",
        "internal_reason",
        "internal-reason",
        "orchestration",
        "rounds",
        "directive",
        "reviewer",
        "verdict",
        "evidence_node_ids",
        "workflow",
        "selector",
    }
)


def test_eval_replay_harness_over_real_fixtures(capsys) -> None:
    exit_code = eval_replay.main([])

    output = capsys.readouterr().out
    assert exit_code == 0, output
    assert "SCENARIOS=4" in output
    assert output.count("SCENARIO ") == 4
    assert "supported_text_delivered" in output
    assert "round_cap_capped" in output
    assert "image_capability_unavailable" in output
    assert "local_model_failure_blocked" in output
    assert "SUMMARY scenarios=4" in output


def test_harness_denylist_is_superset_of_production() -> None:
    # Closes the forbidden-key drift gap: a harness set that ever drops below
    # production would silently shrink the no-engineering-keys regression net.
    missing = _PRODUCTION_FORBIDDEN_KEYS - eval_replay.FORBIDDEN_VIEW_KEYS
    assert not missing, f"harness FORBIDDEN_VIEW_KEYS missing production keys: {sorted(missing)}"
