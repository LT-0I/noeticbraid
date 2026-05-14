# OMC knowledge extraction

- extracted_at: 2026-05-13T00:00:00Z
- source_count: 2
- section_count: 15

## Sources

- ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:cc266f5bcbbfacc9
- ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_rtk_md_sample.md:9fe007d9d7ca790f

## Sections

### oh-my-claudecode - Intelligent Multi-Agent Orchestration

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:4-8

```
# oh-my-claudecode - Intelligent Multi-Agent Orchestration

You are running with oh-my-claudecode (OMC), a multi-agent orchestration layer for Claude Code.
Coordinate specialized agents, tools, and skills so work is completed accurately and efficiently.

```

### operating_principles

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:9-15

```
<operating_principles>
- Delegate specialized work to the most appropriate agent.
- Prefer evidence over assumptions: verify outcomes before final claims.
- Choose the lightest-weight path that preserves quality.
- Consult official docs before implementing with SDKs/frameworks/APIs.
</operating_principles>

```

### delegation_rules

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:16-21

```
<delegation_rules>
Delegate for: multi-file changes, refactors, debugging, reviews, planning, research, verification.
Work directly for: trivial ops, small clarifications, single commands.
Route code to `executor` (use `model=opus` for complex work). Uncertain SDK usage → `document-specialist` (repo docs first; Context Hub / `chub` when available, graceful web fallback otherwise).
</delegation_rules>

```

### model_routing

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:22-26

```
<model_routing>
`haiku` (quick lookups), `sonnet` (standard), `opus` (architecture, deep analysis).
Direct writes OK for: `~/.claude/**`, `.omc/**`, `.claude/**`, `CLAUDE.md`, `AGENTS.md`.
</model_routing>

```

### skills

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:27-34

```
<skills>
Invoke via `/oh-my-claudecode:<name>`. Trigger patterns auto-detect keywords.
Tier-0 workflows include `autopilot`, `ultrawork`, `ralph`, `team`, and `ralplan`.
Keyword triggers: `"autopilot"→autopilot`, `"ralph"→ralph`, `"ulw"→ultrawork`, `"ccg"→ccg`, `"ralplan"→ralplan`, `"deep interview"→deep-interview`, `"deslop"`/`"anti-slop"`→ai-slop-cleaner, `"deep-analyze"`→analysis mode, `"tdd"`→TDD mode, `"deepsearch"`→codebase search, `"ultrathink"`→deep reasoning, `"cancelomc"`→cancel.
Team orchestration is explicit via `/team`.
Detailed agent catalog, tools, team pipeline, commit protocol, and full skills registry live in the native `omc-reference` skill when skills are available, including reference for `explore`, `planner`, `architect`, `executor`, `designer`, and `writer`; this file remains sufficient without skill support.
</skills>

```

### verification

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:35-39

```
<verification>
Verify before claiming completion. Size appropriately: small→haiku, standard→sonnet, large/security→opus.
If verification fails, keep iterating.
</verification>

```

### execution_protocols

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:40-46

```
<execution_protocols>
Broad requests: explore first, then plan. 2+ independent tasks in parallel. `run_in_background` for builds/tests.
Keep authoring and review as separate passes: writer pass creates or revises content, reviewer/verifier pass evaluates it later in a separate lane.
Never self-approve in the same active context; use `code-reviewer` or `verifier` for the approval pass.
Before concluding: zero pending tasks, tests passing, verifier evidence collected.
</execution_protocols>

```

### hooks_and_context

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:47-52

```
<hooks_and_context>
Hooks inject `<system-reminder>` tags. Key patterns: `hook success: Success` (proceed), `[MAGIC KEYWORD: ...]` (invoke skill), `The boulder never stops` (ralph/ultrawork active).
Persistence: `<remember>` (7 days), `<remember priority>` (permanent).
Kill switches: `DISABLE_OMC`, `OMC_SKIP_HOOKS` (comma-separated).
</hooks_and_context>

```

### cancellation

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:53-56

```
<cancellation>
`/oh-my-claudecode:cancel` ends execution modes. Cancel when done+verified or blocked. Don't cancel if work incomplete.
</cancellation>

```

### worktree_paths

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:57-60

```
<worktree_paths>
State: `.omc/state/`, `.omc/state/sessions/{sessionId}/`, `.omc/notepad.md`, `.omc/project-memory.json`, `.omc/plans/`, `.omc/research/`, `.omc/logs/`
</worktree_paths>

```

### Setup

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_claude_md_sample.md:61-66

```
## Setup

Say "setup omc" or run `/oh-my-claudecode:omc-setup`.
<!-- OMC:END -->

@RTK.md
```

### RTK - Rust Token Killer

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_rtk_md_sample.md:1-4

```
# RTK - Rust Token Killer

**Usage**: Token-optimized CLI proxy (60-90% savings on dev operations)

```

### Meta Commands (always use rtk directly)

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_rtk_md_sample.md:5-13

```
## Meta Commands (always use rtk directly)

```bash
rtk gain              # Show token savings analytics
rtk gain --history    # Show command usage history with savings
rtk discover          # Analyze Claude Code history for missed opportunities
rtk proxy <cmd>       # Execute raw command without filtering (for debugging)
```
```

### Installation Verification

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_rtk_md_sample.md:14-23

```
## Installation Verification

```bash
rtk --version         # Should show: rtk X.Y.Z
rtk gain              # Should work (not "command not found")
which rtk             # Verify correct binary
```

```

### Hook-Based Usage

- source: ~/workspace/noeticmind/noeticbraid/packages/noeticbraid-backend/tests/fixtures/omc_source_rtk_md_sample.md:24-29

```
## Hook-Based Usage

All other commands are automatically rewritten by the Claude Code hook.
Example: `git status` → `rtk git status` (transparent, 0 tokens overhead)

Refer to CLAUDE.md for full command reference.
```
