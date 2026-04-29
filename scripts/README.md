# scripts/

Stage 0 scripts are gate helpers only. They do not implement NoeticBraid business features.

- Python scripts are authoritative.
- PowerShell wrappers call Python implementations.
- `apply_legacy_readonly.ps1` is the only native PowerShell script because it applies Windows ACLs.
