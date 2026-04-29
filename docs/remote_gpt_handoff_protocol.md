# Remote GPT Handoff Protocol

NoeticBraid uses a local/remote development loop:

```text
local files + local review notes
→ user uploads to GPT-5.5 Pro Web
→ GPT outputs project artifacts or planning
→ user downloads artifacts
→ local Claude Code + Codex review, test, and integrate
```

## Roles

- GPT-5.5 Pro Web: project artifacts, code, tests, planning, and draft specs when requested.
- Local Claude Code: workflow orchestration, prompts, contract owner actions, integration commits, and local review coordination.
- Local Codex: adversarial review, test review, and second-pass correctness checks.
- User: decisions, resource provision, and handoff execution.

## Workflow hard rules referenced by Stage 0

Hard rule 6: when a step asks for file output, the full content must be delivered as real downloadable files, not pasted as a long chat message. The chat response should contain only a short summary and links.

Hard rule 7: Stage 5 and later use zip-package delivery for project artifacts. The package must include a manifest, checksum file, and stable English filenames.

## File naming convention

- response documents use lowercase English names with underscores;
- project packages use explicit phase and stage names;
- Stage 0 package name is `noeticbraid_phase1_1_stage0.zip`;
- task cards use `TASK-1.1.X_*.md`;
- contract files use `phase1_1_*` names.

## Stage 0 handoff rule

This package is generated as a zip and reviewed in a response area before it is copied into the real project directory.

## Future handoff bundle

A future `handoff_bundle` should include:

- project tree summary;
- changed files;
- current contract version;
- open decisions;
- failing tests;
- local review notes;
- precise next task card.
