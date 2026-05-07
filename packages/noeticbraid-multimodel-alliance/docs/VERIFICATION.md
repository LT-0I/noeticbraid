# Verification

Last full verification is recorded in `BUILD_RECORD.md` after final packaging.

Recommended local gates:

```powershell
python -m pytest -q
python -m compileall -q multimodel_alliance
python -m multimodel_alliance validate-fixtures
python -m multimodel_alliance route examples/task_card_medium.json --pretty
python -m multimodel_alliance run-fixture multimodel_alliance/fixtures/dual_review_prompt_cycle.json --pretty
python C:\Users\13080\Desktop\HBA\GPT5_Workflow\.codex\scripts\license_check_gate.py --package jsonschema pytest setuptools
```
