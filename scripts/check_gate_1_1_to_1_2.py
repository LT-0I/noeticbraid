from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS = [
    ("docs/contracts/phase1_1_api_contract.md", "contract overview exists"),
    ("docs/contracts/phase1_1_pydantic_schemas.py", "contract stub exists"),
    ("docs/contracts/fixtures/_README.md", "draft fixture status exists"),
    ("docs/tasks/TASK-1.1.4_schema.md", "schema task card exists"),
]


def main() -> int:
    ok = True
    print("Gate 1.1 -> 1.2 framework")
    for rel, desc in CHECKS:
        exists = (ROOT / rel).exists()
        print(f"{'PASS' if exists else 'FAIL':4}  {rel}  # {desc}")
        ok = ok and exists
    print("TODO: add schema 1.0.0 freeze and contract_diff checks after TASK-1.1.4.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
