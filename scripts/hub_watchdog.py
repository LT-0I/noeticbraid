#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""HUB MCP watchdog: on a failed HUB MCP capability, file a deduped GitHub
issue; when the issue is closed (human fixed it), self-verify and signal
RESUME so dependent work can continue without manual coordination.

Modes:
  --probe                 run the safe read-only HUB health probe (cron mode)
  --report KEY "MSG"      record a specific HUB-call failure observed during work
  --status                print current watchdog state + open issues

Honest-Q4: only real probe results are reported; a capability is never
declared healthy unless the probe actually passes. Two-zone / IP-safe:
issue text is whitelisted to capability name + classified reason code +
guidance + UTC timestamp — never paths, cookies, tokens, sha, conv ids.
No new dependency (stdlib + the gh CLI + scripts/hub-mcp.sh only).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Issues are filed in the HUB's OWN repo — that is where an MCP/capability
# problem actually gets fixed. The watchdog polls there; on close it
# re-verifies and re-injects the capability into our workflow.
REPO = "LT-0I/web-ai-capability-hub"
LABEL = "hub-watchdog"
ROOT = Path(__file__).resolve().parent.parent
HUB_MCP = ROOT / "scripts" / "hub-mcp.sh"
STATE_PATH = ROOT / ".hub-watchdog-state.json"          # gitignored
MARKER = "watchdog-key:"                                  # stable dedup marker in issue body
COMMENT_MIN_INTERVAL_S = 50 * 60                          # rate-limit re-failure comments
CALL_TIMEOUT_S = 25

# Whitelisted health probe (read-only; never a generation/account-burning op).
PROBE_TARGETS = (("gemini", "gemini"), ("chatgpt", "chatgpt"), ("claude", "claude"))

_REDACT = re.compile(
    r"(/[\w.\-/]+)|([A-Za-z]:\\[\\\w.\-]+)|(gho_\w+|sk-\w+|eyJ[\w.\-]+)|([0-9a-f]{32,})",
)


def _sanitize(text: str, *, cap: int = 240) -> str:
    """Strip path/token/hex-ish substrings; collapse whitespace; cap length."""
    cleaned = _REDACT.sub("[redacted]", str(text or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:cap]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"keys": {}}


def _save_state(state: dict) -> None:
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, STATE_PATH)


def _gh(args: list[str], *, check: bool = False) -> subprocess.CompletedProcess:
    # gh uses the keyring identity (same as git push); GH_TOKEN/GITHUB_TOKEN
    # are intentionally unset to mirror the repo's push auth.
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN")}
    return subprocess.run(
        ["gh", *args], capture_output=True, text=True, env=env,
        timeout=60, check=check,
    )


def _mcp_call(messages: list[dict]) -> list[dict]:
    """Drive scripts/hub-mcp.sh over stdio JSON-RPC; return parsed responses."""
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    try:
        proc = subprocess.run(
            ["bash", str(HUB_MCP)], input=payload, capture_output=True,
            text=True, timeout=CALL_TIMEOUT_S + 10,
        )
    except subprocess.TimeoutExpired:
        return [{"_transport": "timeout"}]
    out = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    if not out:
        return [{"_transport": "no_response", "_stderr": proc.stderr[-200:]}]
    return out


def _probe() -> dict:
    """Return {key: {ok, reason, guidance}} for transport + per-target health.

    Distinguishes infra failure (issue-worthy as a bug) from honest-blocked
    (issue-worthy as 'needs login/gate' — actionable, the user closes it
    once fixed and the watchdog re-verifies)."""
    results: dict[str, dict] = {}
    init = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "watchdog", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    resp = _mcp_call(init)
    if any("_transport" in r for r in resp):
        results["hub.transport"] = {
            "ok": False, "reason": "MCP server transport failure (no JSON-RPC response)",
            "guidance": "HUB MCP server failed to start/respond. Check the hub build "
                        "(`npm run build` in web-ai-capability-hub) and scripts/hub-mcp.sh.",
        }
        return results  # nothing else reachable
    tools = next((r for r in resp if r.get("id") == 2), {})
    n_tools = len((tools.get("result") or {}).get("tools", []))
    results["hub.transport"] = {
        "ok": n_tools > 0,
        "reason": "ok" if n_tools > 0 else "tools/list returned no tools",
        "guidance": "" if n_tools > 0 else "HUB MCP server up but exposed 0 tools.",
    }
    for target, profile in PROBE_TARGETS:
        msgs = init + [{
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "consumer_health",
                       "arguments": {"target": target, "profile": profile}}}]
        r = _mcp_call(msgs)
        node = next((m for m in r if m.get("id") == 3), {})
        key = f"hub.health.{target}"
        if "_transport" in (r[0] if r else {}):
            results[key] = {"ok": False, "reason": "transport failure during health call",
                            "guidance": "HUB MCP became unresponsive mid-probe."}
            continue
        err = node.get("error")
        body = ""
        if isinstance(node.get("result"), dict):
            for c in node["result"].get("content", []):
                if c.get("type") == "text":
                    body += c.get("text", "")
        healthy = False
        reason = "unknown"
        guidance = ""
        if err:
            reason = f"MCP error: {_sanitize(err.get('message'))}"
            guidance = "HUB returned an MCP-level error for consumer_health."
        else:
            try:
                parsed = json.loads(body) if body.strip().startswith("{") else {}
            except Exception:
                parsed = {}
            if parsed.get("ok") is True or parsed.get("healthy") is True:
                healthy = True
                reason = "ok"
            else:
                code = parsed.get("errorCode") or parsed.get("error_code") or ""
                reason = _sanitize(parsed.get("error") or code or body or "not healthy")
                low = (reason + " " + str(code)).lower()
                if "login" in low or "auth" in low or "consent" in low or "sign" in low:
                    guidance = (f"The `{profile}` web profile likely needs a manual "
                                f"login in its visible browser (hub never bypasses login).")
                elif "gate" in low or "automation" in low or "hub_exec" in low or "digest" in low:
                    guidance = ("HUB egress gate is off — set NOETICBRAID_PLATFORM_HUB_EXEC "
                                "and ensure automation/digest/health gates pass.")
                elif "page" in low or "target" in low or "missing" in low or "not found" in low:
                    guidance = (f"No live `{profile}` browser page — launch it: "
                                f"scripts/hub-browser.sh browser:launch --profile {profile} "
                                f"--url <{target} site> --json (then log in if prompted).")
                else:
                    guidance = f"consumer_health for `{target}` is not ok."
        results[key] = {"ok": healthy, "reason": reason, "guidance": guidance}
    return results


def _find_open_issue(key: str) -> int | None:
    r = _gh(["issue", "list", "-R", REPO, "--label", LABEL, "--state", "open",
             "--search", f'"{MARKER} {key}"', "--json", "number,body", "-L", "20"])
    if r.returncode != 0:
        return None
    try:
        for it in json.loads(r.stdout or "[]"):
            if f"{MARKER} {key}" in (it.get("body") or ""):
                return int(it["number"])
    except Exception:
        return None
    return None


def _issue_state(num: int) -> str:
    r = _gh(["issue", "view", str(num), "-R", REPO, "--json", "state"])
    try:
        return json.loads(r.stdout)["state"].lower()
    except Exception:
        return "unknown"


def _open_issue(key: str, reason: str, guidance: str) -> int | None:
    title = f"[hub-watchdog] HUB capability unavailable: {key}"
    body = (
        f"{MARKER} {key}\n\n"
        f"The HUB MCP watchdog detected that **{key}** is not usable.\n\n"
        f"- Classified reason: `{_sanitize(reason)}`\n"
        f"- What to do: {_sanitize(guidance, cap=400) or 'investigate the HUB capability'}\n"
        f"- First observed (UTC): {_now()}\n\n"
        f"This issue was filed automatically so work can proceed without manual "
        f"coordination. **Close this issue once you've fixed the underlying "
        f"capability** (e.g. logged the web profile in / enabled the gate). The "
        f"watchdog scans every ~10 min, re-verifies on close, and resumes "
        f"automatically. It will reopen this with a note if re-verification "
        f"still fails. (No paths/credentials are included by design.)"
    )
    r = _gh(["issue", "create", "-R", REPO, "--title", title, "--label", LABEL,
             "--body", body])
    m = re.search(r"/issues/(\d+)", r.stdout or "")
    return int(m.group(1)) if m else None


def _comment(num: int, msg: str) -> None:
    _gh(["issue", "comment", str(num), "-R", REPO, "--body", _sanitize(msg, cap=400)])


def _close(num: int, msg: str) -> None:
    _gh(["issue", "close", str(num), "-R", REPO, "--comment", _sanitize(msg, cap=400)])


def _reopen(num: int, msg: str) -> None:
    _gh(["issue", "reopen", str(num), "-R", REPO])
    _comment(num, msg)


def _ensure_issue(state: dict, key: str, reason: str, guidance: str) -> None:
    rec = state["keys"].get(key, {})
    num = rec.get("issue") or _find_open_issue(key)
    now = time.time()
    if num is None:
        num = _open_issue(key, reason, guidance)
        if num is not None:
            print(f"FILED: #{num} {key} :: {reason}")
    else:
        if now - rec.get("last_comment_ts", 0) > COMMENT_MIN_INTERVAL_S:
            _comment(num, f"Still failing as of {_now()} — reason: {reason}")
            rec["last_comment_ts"] = now
        print(f"OPEN: #{num} {key} (still failing)")
    state["keys"][key] = {**rec, "issue": num, "status": "failing",
                          "reason": reason, "last_seen_fail": _now(),
                          "last_comment_ts": rec.get("last_comment_ts", now)}


def _resolve_if_fixed(state: dict, key: str, healthy: bool, reason: str) -> None:
    rec = state["keys"].get(key)
    if not rec or not rec.get("issue"):
        if healthy:
            state["keys"].pop(key, None)
        return
    num = rec["issue"]
    gh_state = _issue_state(num)
    if gh_state == "closed":
        if healthy:
            _comment(num, f"Auto-verified: {key} is healthy again as of {_now()}. "
                          f"Resuming dependent work.")
            print(f"RESUME: {key} (#{num} closed by human, re-verified PASS)")
            state["keys"].pop(key, None)
        else:
            _reopen(num, f"Auto-reverify after close still FAILS as of {_now()} — "
                         f"reason: {reason}. Reopening (honest: not yet fixed).")
            print(f"REOPEN: #{num} {key} (closed but still failing)")
            rec["status"] = "failing"
    else:
        if healthy:
            _close(num, f"Auto-resolved: {key} healthy again as of {_now()}.")
            print(f"RESUME: {key} (#{num} auto-closed, re-verified PASS)")
            state["keys"].pop(key, None)
        else:
            print(f"OPEN: #{num} {key} (still failing)")


def cmd_probe() -> int:
    state = _load_state()
    results = _probe()
    any_fail = False
    for key, r in results.items():
        if r["ok"]:
            _resolve_if_fixed(state, key, True, r["reason"])
        else:
            any_fail = True
            # honest-blocked still gets an issue: it is the actionable signal.
            if key in state["keys"] and state["keys"][key].get("issue"):
                _resolve_if_fixed(state, key, False, r["reason"])
            else:
                _ensure_issue(state, key, r["reason"], r.get("guidance", ""))
    _save_state(state)
    print(f"watchdog: {sum(1 for v in results.values() if v['ok'])}/{len(results)} healthy "
          f"@ {_now()}")
    return 1 if any_fail else 0


def cmd_report(key: str, msg: str) -> int:
    state = _load_state()
    _ensure_issue(state, _sanitize(key, cap=64) or "hub.unknown",
                  _sanitize(msg), "Reported by an in-flight HUB-dependent task.")
    _save_state(state)
    return 0


def cmd_status() -> int:
    state = _load_state()
    print(json.dumps(state, indent=2, sort_keys=True))
    r = _gh(["issue", "list", "-R", REPO, "--label", LABEL, "--state", "open",
             "--json", "number,title", "-L", "30"])
    print("open watchdog issues:", r.stdout.strip() or "[]")
    return 0


def main(argv: list[str]) -> int:
    if "--report" in argv:
        i = argv.index("--report")
        return cmd_report(argv[i + 1], argv[i + 2] if len(argv) > i + 2 else "")
    if "--status" in argv:
        return cmd_status()
    return cmd_probe()  # default / --probe


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
