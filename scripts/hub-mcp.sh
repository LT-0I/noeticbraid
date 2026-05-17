#!/usr/bin/env bash
# Ported HUB MCP launcher (web-ai-research-automation-hub).
#
# The HUB is referenced IN PLACE — its 11 GB of credentialed browser
# profiles (data/browser-profiles/*) are NOT vendored into this repo.
# The hub resolves its data dir as `path.resolve(process.cwd(), "data")`
# (it ignores WAH_DATA_DIR), so this launcher runs the MCP server with
# cwd = the hub checkout. That makes the hub use its own in-place
# profiles; nothing credentialed ever enters this repo tree.
set -euo pipefail

HUB_DIR="${WAH_HUB_DIR:-/home/l1u/workspace/noeticmind/web-ai-capability-hub}"

if [[ ! -f "$HUB_DIR/dist/src/cli.js" ]]; then
  echo "hub-mcp: HUB build not found at $HUB_DIR/dist/src/cli.js (run 'npm run build' in the hub)" >&2
  exit 1
fi

cd "$HUB_DIR"
exec node dist/src/cli.js mcp "$@"
