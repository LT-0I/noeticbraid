# reuse_log/

Every stage must create a reuse candidate log before implementation begins.

Rules:

- do not reinvent features that an active compatible open-source project already solves well;
- every direct dependency requires license review;
- AGPL or unknown-license projects cannot enter Apache-2.0 core;
- `license_status: pending_review` means local double review has not approved use yet.
