#!/usr/bin/env bash
# Ported HUB browser-launch method (web-ai-research-automation-hub).
#
# Thin pass-through to the hub CLI run with cwd = the hub checkout so it
# uses its IN-PLACE credentialed profiles (data/browser-profiles/*) — no
# profile data is vendored into this repo.
#
# Usage:
#   scripts/hub-browser.sh browser:launch --profile gemini  --url https://gemini.google.com/app --json
#   scripts/hub-browser.sh browser:launch --profile chatgpt --url https://chatgpt.com           --json
#   scripts/hub-browser.sh browser:status --profile gemini  --json
#   scripts/hub-browser.sh browser:pages  --profile gemini  --json
#   scripts/hub-browser.sh browser:close  --profile gemini  --mode disconnect --json
#
# Profiles policy (hub): one per service — chatgpt, claude, gemini,
# research-default, plus the institutional nuaa-* profiles. The user logs
# in manually in the visible browser; the hub never imports/exports cookies.
set -euo pipefail

HUB_DIR="${WAH_HUB_DIR:-/home/l1u/workspace/noeticmind/web-ai-capability-hub}"

if [[ ! -f "$HUB_DIR/dist/src/cli.js" ]]; then
  echo "hub-browser: HUB build not found at $HUB_DIR/dist/src/cli.js (run 'npm run build' in the hub)" >&2
  exit 1
fi
if [[ $# -eq 0 ]]; then
  echo "usage: hub-browser.sh browser:launch --profile <name> --url <url> --json  (see header for more)" >&2
  exit 2
fi

cd "$HUB_DIR"
exec node dist/src/cli.js "$@"
