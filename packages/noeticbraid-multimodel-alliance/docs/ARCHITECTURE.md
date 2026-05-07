# SP-B Architecture

## Scope

SP-B is the decision layer for the NoeticBraid 9-SP topology. It owns three records:

1. `ModelRoute`: which model roles should participate and why.
2. `Debate`: what each participant produced, reviewed, objected to, or verified.
3. `Convergence`: which objections are accepted, rejected, or carried to user/evidence decisions.

It deliberately does **not** invoke models, browse, persist data, update RunRecord event types, or modify frozen OpenAPI contracts.

## Components

- `router.py`: deterministic rule table from task card to `ModelRoute`.
- `debate_runner.py`: converts external round inputs into structured `Debate` records.
- `convergence.py`: partitions objections into accepted/rejected/unresolved outcomes.
- `validator.py`: combines JSON Schema validation with module invariants and private-marker scanning.
- `cli.py`: file-oriented command surface for local testing and handoff.

## Frozen contract alignment

The packaged `model_route.schema.json` keeps the 13 required fields and aligns role enums with the frozen `ModelRoute 1.2.0` boundary, including `human_decision`. `workflow_id` is optional and does not change required-field count. Existing three fixtures remain valid.

## Routing rules

- `risk=low`: `single_model` if exactly one sufficient model and no coding/review/evidence/convergence capability is requested; otherwise `producer_reviewer`.
- `risk=medium`: `dual_review` with producer, two reviewers, and convergence editor.
- `risk=high`: `multi_review` with producer/coder, reviewer, adversary, verifier, and convergence editor.
- `risk=disputed` or `disputed=true`: `manual_convergence` with reviewer, adversary, convergence editor, and `human_decision`.

## Integration notes

Main-repo target path remains `noeticbraid/tools/multimodel_alliance/`. This standalone SP package is ready for a later controlled integration cycle; it does not write `state.json` or `RunRecord` itself.
