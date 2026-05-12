# OMC Debate Loop (SDD-D2-01)

Manual smoke:

```bash
PYTHONPATH=noeticbraid/packages/noeticbraid-multimodel-alliance/src \
python -m noeticbraid.tools.multimodel_alliance debate-loop \
  noeticbraid/packages/noeticbraid-multimodel-alliance/examples/task_card_omc_ingest.json \
  --mock-invocations \
  --state-root "$(mktemp -d)" \
  --artifact-root "$(mktemp -d)" \
  --pretty
```

Artifact chain:

1. fixed three-model `ModelRoute` JSON;
2. mock/manual provider artifact summaries;
3. structured `Debate` JSON;
4. structured `Convergence` JSON;
5. program-memory candidate JSONL under `state/program_memory/candidates/`;
6. concise convergence markdown generated from structured records;
7. RunRecord-shaped ledger JSONL using only `artifact_created`, `routing_advice_recorded`, and `lesson_candidate_created`.

Boundaries: no scheduler/cron/b-1 auto trigger, no backend contract change, no vault/raw-note writes, no confirmed-memory writes, and no live provider calls unless `provider_mode=True` is explicitly supplied.
