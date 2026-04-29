"""Contract diff gate.

Compare Stage 1 implementation schemas (packages/noeticbraid-core/src/noeticbraid_core/schemas/)
against the contract stub (docs/contracts/phase1_1_pydantic_schemas.py) by running
model_json_schema() on both sides and checking equivalence on:

- field name set per model
- bare type signatures (str / int / Optional[str] / list[str] / datetime / Literal[...])
- Literal enum value sets

Constraints (Field/default/ge/le/min_length/max_length/pattern/validator/Config/methods)
are NOT compared. The stub keeps bare-shape only; constraints live in
docs/contracts/phase1_1_api_contract.md §20 + stub CONTRACT_NOTE comments.

Exit code: 0 = PASS, 1 = FAIL (any divergence).
Stdout: per-model report.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
IMPL_PKG = REPO_ROOT / "packages" / "noeticbraid-core" / "src"
STUB_PATH = REPO_ROOT / "docs" / "contracts" / "phase1_1_pydantic_schemas.py"
MODEL_NAMES = ["Task", "RunRecord", "SourceRecord", "ApprovalRequest", "SideNote", "DigestionItem"]


def load_implementation_models() -> dict[str, Any]:
    sys.path.insert(0, str(IMPL_PKG))
    try:
        from noeticbraid_core.schemas import (  # type: ignore  # noqa: E402
            ApprovalRequest,
            DigestionItem,
            RunRecord,
            SideNote,
            SourceRecord,
            Task,
        )
    finally:
        sys.path.remove(str(IMPL_PKG))
    return {
        "Task": Task,
        "RunRecord": RunRecord,
        "SourceRecord": SourceRecord,
        "ApprovalRequest": ApprovalRequest,
        "SideNote": SideNote,
        "DigestionItem": DigestionItem,
    }


def load_stub_models() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("phase1_1_stub", STUB_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load stub at {STUB_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return {name: getattr(module, name) for name in MODEL_NAMES}


def field_set(model: Any) -> set[str]:
    return set(model.model_fields.keys())


def bare_type_signature(model: Any) -> dict[str, str]:
    """Reduce field annotations to bare-type strings, ignoring Field/constraints."""

    sig: dict[str, str] = {}
    for fname, finfo in model.model_fields.items():
        # Use repr of annotation; both stub and impl share the same Python type
        # (datetime / Optional[str] / list[str] / Literal[...] etc.)
        sig[fname] = repr(finfo.annotation)
    return sig


def literal_values(model: Any) -> dict[str, tuple]:
    """Extract Literal value tuples per field, empty tuple if not Literal."""

    import typing

    out: dict[str, tuple] = {}
    for fname, finfo in model.model_fields.items():
        ann = finfo.annotation
        origin = typing.get_origin(ann)
        # Optional[Literal] unpack
        if origin in (typing.Union,) or (hasattr(typing, "UnionType") and isinstance(origin, getattr(typing, "UnionType", type(None)))):
            for arg in typing.get_args(ann):
                if typing.get_origin(arg) is typing.Literal:
                    out[fname] = tuple(typing.get_args(arg))
                    break
            else:
                out[fname] = ()
        elif origin is typing.Literal:
            out[fname] = tuple(typing.get_args(ann))
        else:
            out[fname] = ()
    return out


def diff_model(name: str, impl: Any, stub: Any) -> list[str]:
    errors: list[str] = []
    if field_set(impl) != field_set(stub):
        errors.append(
            f"{name}: field set mismatch | impl={sorted(field_set(impl))} | stub={sorted(field_set(stub))}"
        )
    impl_sig = bare_type_signature(impl)
    stub_sig = bare_type_signature(stub)
    for fname in sorted(set(impl_sig) | set(stub_sig)):
        if impl_sig.get(fname) != stub_sig.get(fname):
            errors.append(
                f"{name}.{fname}: bare type mismatch | impl={impl_sig.get(fname)} | stub={stub_sig.get(fname)}"
            )
    impl_lit = literal_values(impl)
    stub_lit = literal_values(stub)
    for fname in sorted(set(impl_lit) | set(stub_lit)):
        if set(impl_lit.get(fname, ())) != set(stub_lit.get(fname, ())):
            errors.append(
                f"{name}.{fname}: Literal value set mismatch | impl={impl_lit.get(fname)} | stub={stub_lit.get(fname)}"
            )
    return errors


def main() -> int:
    impl_models = load_implementation_models()
    stub_models = load_stub_models()
    all_errors: list[str] = []
    for name in MODEL_NAMES:
        impl = impl_models[name]
        stub = stub_models[name]
        errs = diff_model(name, impl, stub)
        if errs:
            print(f"[FAIL] {name}: {len(errs)} divergence(s)")
            for e in errs:
                print(f"  - {e}")
            all_errors.extend(errs)
        else:
            print(f"[PASS] {name}: field set + bare types + Literal values equivalent")
    print()
    if all_errors:
        print(f"contract_diff: FAIL ({len(all_errors)} total divergence(s))")
        return 1
    print("contract_diff: PASS (6 models equivalent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
