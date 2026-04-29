# Contract Change Requests

Contract changes after `1.0.0` must be proposed through this directory.

Flow:

1. Submitter fills `_template.md` and creates `docs/contracts/contract_change_requests/{request_id}.md`.
2. Local main Claude session reviews.
3. Codex xhigh review checks compatibility and impact.
4. User approves or rejects.
5. Only after approval may the local owner update contract files and broadcast the new version.

Before approval, do not modify:

- `phase1_1_pydantic_schemas.py`;
- `phase1_1_openapi.yaml`;
- `fixtures/**`.

Expedited changes are allowed only for blocking errors and still require an audit trail after the fact.
