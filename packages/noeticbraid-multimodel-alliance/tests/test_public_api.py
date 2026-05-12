from __future__ import annotations

from pathlib import Path


def test_public_api_imports():
    from noeticbraid.tools.multimodel_alliance import converge, route, run_debate, run_debate_loop

    assert callable(route)
    assert callable(run_debate)
    assert callable(converge)
    assert callable(run_debate_loop)


def test_static_artifacts_are_packaged():
    root = Path(__file__).resolve().parents[1]
    package = root / "src" / "noeticbraid" / "tools" / "multimodel_alliance"
    for rel in [
        "schemas/model_route.schema.json",
        "schemas/debate.schema.json",
        "schemas/convergence.schema.json",
        "fixtures/dual_review_prompt_cycle.json",
        "fixtures/multi_review_high_risk_gate.json",
        "fixtures/manual_convergence_disputed.json",
        "fixtures/omc_debate_loop_mock.json",
        "fixtures/omc_convergence_markdown_golden.md",
    ]:
        assert (package / rel).is_file(), rel

    # Runtime imports may create __pycache__; the migrated static artifacts must not contain copied caches.
    static_dirs = [package / "schemas", package / "fixtures"]
    forbidden = []
    for static_dir in static_dirs:
        forbidden.extend(static_dir.rglob("__pycache__"))
        forbidden.extend(static_dir.rglob("*.pyc"))
    assert forbidden == []
