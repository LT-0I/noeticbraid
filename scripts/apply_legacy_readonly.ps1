param(
  [string]$LegacyPath = "$PSScriptRoot/../legacy/helixmind_phase1"
)

Write-Host "Applying read-only marker to $LegacyPath"
if (-not (Test-Path $LegacyPath)) {
  Write-Error "Legacy path does not exist: $LegacyPath"
  exit 1
}

# Stage 0 helper: set read-only attribute recursively.
# Local owner may replace this with stricter ACL policy after review.
Get-ChildItem -Path $LegacyPath -Recurse -Force | ForEach-Object { $_.IsReadOnly = $true }
Write-Host "Legacy path marked read-only."
