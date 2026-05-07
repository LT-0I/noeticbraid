"""Constants shared by SP-B multimodel alliance runtime modules."""

from __future__ import annotations

SCHEMA_FILES = (
    "model_route.schema.json",
    "debate.schema.json",
    "convergence.schema.json",
)

FIXTURE_FILES = (
    "dual_review_prompt_cycle.json",
    "manual_convergence_disputed.json",
    "multi_review_high_risk_gate.json",
)

SCHEMA_BY_RECORD = {
    "model_route": "model_route.schema.json",
    "route": "model_route.schema.json",
    "debate": "debate.schema.json",
    "convergence": "convergence.schema.json",
}

ROUTE_TYPES = {"single_model", "producer_reviewer", "dual_review", "multi_review", "manual_convergence"}
TRIGGERS = {"user_request", "task_card", "workflow_step", "review_gate", "failure_recovery"}
RISK_LEVELS = {"low", "medium", "high", "disputed"}
CAPABILITIES = {
    "planning",
    "research",
    "writing",
    "coding",
    "code_review",
    "adversary",
    "source_audit",
    "browser",
    "file_io",
    "verification",
    "security_review",
    "convergence",
}
MODEL_ROLES = {
    "orchestrator",
    "planner",
    "researcher",
    "producer",
    "writer",
    "coder",
    "reviewer",
    "adversary",
    "source_auditor",
    "verifier",
    "convergence_editor",
    "human_decision",
}
PARTICIPANT_ROLES = {
    "producer",
    "reviewer",
    "adversary",
    "source_auditor",
    "logic_reviewer",
    "verifier",
    "convergence_editor",
}
EXPECTED_OUTPUTS = {"plan", "patch", "report", "verdict", "risk_list", "evidence", "minority_opinion", "validation_result"}
ROUND_TYPES = {"production", "review", "adversarial_review", "verification", "arbitration"}
VERDICTS = {"pass", "partial", "fail", "concern", "informational"}
SEVERITIES = {"critical", "high", "medium", "low"}
OBJECTION_STATUSES = {"raised", "accepted", "rejected", "unresolved", "needs_user_decision"}
DECISION_STATUSES = {"accepted", "needs_user_decision", "needs_more_evidence", "rejected"}
ROUTE_STATUSES = {"draft", "selected", "invoked", "superseded", "failed"}
INVOCATIONS = {"local_session", "codex_cli", "chatgpt_web", "subagent", "manual"}

PRIVATE_MARKERS = tuple(
    "_".join(parts)
    for parts in (
        ("raw", "token"),
        ("token", "hash"),
        ("dpapi", "blob"),
        ("credential", "path"),
        ("profile", "path"),
        ("profile", "dir"),
        ("cookie", "value"),
    )
) + ("." + "git",)

DEFAULT_AVAILABLE_MODELS = (
    {
        "model_ref": "model_claude_main",
        "role": "producer",
        "roles": ["planner", "producer", "writer", "convergence_editor"],
        "capabilities": ["planning", "writing", "convergence"],
        "invocation": "local_session",
    },
    {
        "model_ref": "model_codex_cli",
        "role": "coder",
        "roles": ["coder", "reviewer", "adversary", "verifier"],
        "capabilities": ["coding", "code_review", "adversary", "verification", "security_review", "file_io"],
        "invocation": "codex_cli",
    },
    {
        "model_ref": "model_claude_reviewer_a",
        "role": "reviewer",
        "roles": ["reviewer", "source_auditor"],
        "capabilities": ["code_review", "source_audit", "planning"],
        "invocation": "subagent",
    },
    {
        "model_ref": "model_local_verifier",
        "role": "verifier",
        "roles": ["verifier"],
        "capabilities": ["verification", "file_io"],
        "invocation": "local_session",
    },
    {
        "model_ref": "model_user",
        "role": "human_decision",
        "roles": ["human_decision", "orchestrator"],
        "capabilities": ["convergence"],
        "invocation": "manual",
    },
)
