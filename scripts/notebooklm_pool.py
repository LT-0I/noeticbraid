#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""NotebookLM multi-account pool: enroll / refresh / status.

Enrolls existing **already-logged-in Chrome named profiles** into the
NoeticBraid NotebookLM RPC account pool with **no interactive re-login**:
per Chrome ``Profile N`` it reads the live Google/NotebookLM cookies via
``rookiepy.any_browser`` (profile-targeted), converts them with the upstream
``notebooklm.auth.convert_rookiepy_cookies_to_storage_state`` and writes a
``notebooklm`` profile ``storage_state.json``, then (re)builds the pool
config at the default ``~/.noeticbraid/notebooklm/pool.json``.

This is operational tooling (not a frozen contract / not package surface).
Secrets (storage_state, pool state) live under ``~/.notebooklm`` and
``~/.noeticbraid`` — never in the repo. The account/ToS/quota risk of the
undocumented upstream Google API is the operator's (see the
``noeticbraid-notebooklm-rpc`` package README risk warning).

Usage:
    scripts/notebooklm_pool.py enroll [--profiles 1,2,3|all] [--no-pool]
    scripts/notebooklm_pool.py refresh <nbN|all>
    scripts/notebooklm_pool.py status [--probe]

``status`` lists each enrolled account's auth state (live ``notebooks.list``).
``status --probe`` additionally runs a self-cleaning functional test per
account: create a throwaway notebook -> confirm in list -> delete -> confirm
gone (proves create/list/delete RPC, minimal quota, no residue).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import rookiepy
import notebooklm
import notebooklm.auth as nbauth
from notebooklm.paths import get_storage_path

from noeticbraid.tools.notebooklm_rpc import NotebookLMAccountPool
from noeticbraid.tools.notebooklm_rpc._config_schema import validate_pool_config

CHROME_DIR = Path("~/.config/google-chrome").expanduser()
LOCAL_STATE = CHROME_DIR / "Local State"
POOL_CONFIG = Path("~/.noeticbraid/notebooklm/pool.json").expanduser()
DEFAULT_DAILY_QUOTA = 100
PROBE_TITLE_PREFIX = "nb-healthcheck-"


def _profile_email_map() -> dict[str, str]:
    """Chrome ``Profile N`` -> account email, from Local State info_cache."""
    if not LOCAL_STATE.exists():
        return {}
    info = json.loads(LOCAL_STATE.read_text()).get("profile", {}).get("info_cache", {})
    return {k: (v.get("user_name") or "?") for k, v in info.items()}


def _enrolled_nb_ids() -> list[str]:
    base = Path("~/.notebooklm/profiles").expanduser()
    if not base.exists():
        return []
    return sorted(
        (p.name for p in base.iterdir() if (p / "storage_state.json").exists()),
        key=lambda s: (len(s), s),
    )


def extract_profile(profile_n: int) -> dict:
    """Chrome ``Profile <n>`` cookies -> notebooklm profile ``nb<n>`` storage_state."""
    cp = f"Profile {profile_n}"
    nb_id = f"nb{profile_n}"
    email = _profile_email_map().get(cp, "?")
    db = CHROME_DIR / cp / "Cookies"
    rec: dict = {"chrome": cp, "email": email, "nb": nb_id}
    if not db.exists():
        rec["status"] = "NO_COOKIE_DB"
        return rec
    try:
        cookies = rookiepy.any_browser(
            str(db), sorted(nbauth.ALLOWED_COOKIE_DOMAINS), str(LOCAL_STATE)
        )
    except Exception as exc:  # noqa: BLE001 - report, continue other profiles
        rec["status"] = f"EXTRACT_FAIL:{type(exc).__name__}:{exc}"
        return rec
    ss = nbauth.convert_rookiepy_cookies_to_storage_state(cookies)
    sp = Path(get_storage_path(profile=nb_id))
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(ss))
    os.chmod(sp, 0o600)
    rec.update(
        cookies=len(cookies),
        ss_cookies=len(ss.get("cookies", [])),
        storage=str(sp),
        status="WRITTEN",
    )
    return rec


def build_pool(nb_ids: list[str]) -> dict:
    accounts = []
    emap_by_nb = {
        f"nb{cp.split()[-1]}": em
        for cp, em in _profile_email_map().items()
        if cp.startswith("Profile ")
    }
    for nb_id in nb_ids:
        sp = Path(get_storage_path(profile=nb_id))
        if not sp.exists():
            continue
        accounts.append(
            {
                "account_id": nb_id,
                "storage_state_path": str(sp),
                "daily_quota": DEFAULT_DAILY_QUOTA,
                "label": emap_by_nb.get(nb_id, nb_id),
            }
        )
    cfg = {
        "version": 1,
        "accounts": accounts,
        "selection_policy": "least_recent_success",
    }
    validate_pool_config(cfg)
    POOL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    POOL_CONFIG.write_text(json.dumps(cfg, indent=1, ensure_ascii=False))
    os.chmod(POOL_CONFIG, 0o600)
    return cfg


async def _check_account(nb_id: str, probe: bool) -> dict:
    sp = Path(get_storage_path(profile=nb_id))
    rec: dict = {"nb": nb_id}
    if not sp.exists():
        rec["status"] = "NOT_ENROLLED"
        return rec
    try:
        auth = await notebooklm.AuthTokens.from_storage(path=sp)
        client = notebooklm.NotebookLMClient(auth)
        async with client:
            nbs = await client.notebooks.list()
            rec["auth"] = "OK"
            rec["notebooks"] = len(nbs)
            if probe:
                title = f"{PROBE_TITLE_PREFIX}{int(time.time())}"
                created = await client.notebooks.create(title)
                after = await client.notebooks.list()
                seen = any(getattr(n, "id", None) == created.id for n in after)
                deleted = await client.notebooks.delete(created.id)
                gone = all(
                    getattr(n, "id", None) != created.id
                    for n in await client.notebooks.list()
                )
                rec["probe"] = (
                    "PASS"
                    if (seen and deleted and gone)
                    else f"FAIL(seen={seen},deleted={deleted},gone={gone})"
                )
        rec["status"] = "USABLE" if rec.get("probe", "PASS") == "PASS" else "DEGRADED"
    except Exception as exc:  # noqa: BLE001 - per-account isolation
        rec["status"] = f"FAIL:{type(exc).__name__}:{str(exc)[:120]}"
    return rec


async def _status(nb_ids: list[str], probe: bool) -> list[dict]:
    out = []
    for nb_id in nb_ids:
        out.append(await _check_account(nb_id, probe))
    return out


def _parse_profiles(arg: str) -> list[int]:
    if arg == "all":
        return list(range(1, 9))
    return [int(x) for x in arg.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="notebooklm_pool", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_en = sub.add_parser("enroll", help="extract Chrome profiles -> notebooklm + pool")
    p_en.add_argument("--profiles", default="all", help="e.g. 1,2,5 or 'all' (default)")
    p_en.add_argument("--no-pool", action="store_true", help="skip (re)building pool.json")

    p_rf = sub.add_parser("refresh", help="re-extract one/all enrolled accounts")
    p_rf.add_argument("target", help="nbN or 'all'")

    p_st = sub.add_parser("status", help="per-account auth (+ --probe functional test)")
    p_st.add_argument("--probe", action="store_true", help="create/delete functional test")

    args = ap.parse_args(argv)

    if args.cmd == "enroll":
        recs = [extract_profile(n) for n in _parse_profiles(args.profiles)]
        for r in recs:
            print(json.dumps(r, ensure_ascii=False))
        ok = [r["nb"] for r in recs if r.get("status") == "WRITTEN"]
        if ok and not args.no_pool:
            cfg = build_pool(_enrolled_nb_ids())
            print(f"[pool] {POOL_CONFIG} validated, {len(cfg['accounts'])} accounts")
        return 0 if ok else 1

    if args.cmd == "refresh":
        if args.target == "all":
            nums = [int(x[2:]) for x in _enrolled_nb_ids() if x.startswith("nb")]
        else:
            nums = [int(args.target[2:])]
        recs = [extract_profile(n) for n in nums]
        for r in recs:
            print(json.dumps(r, ensure_ascii=False))
        build_pool(_enrolled_nb_ids())
        print(f"[pool] {POOL_CONFIG} rebuilt")
        return 0 if all(r.get("status") == "WRITTEN" for r in recs) else 1

    if args.cmd == "status":
        nb_ids = _enrolled_nb_ids()
        if not nb_ids:
            print("no enrolled accounts (run: notebooklm_pool.py enroll)")
            return 1
        recs = asyncio.run(_status(nb_ids, args.probe))
        for r in recs:
            print(json.dumps(r, ensure_ascii=False))
        usable = sum(1 for r in recs if r.get("status") == "USABLE")
        print(f"[summary] {usable}/{len(recs)} USABLE"
              + (" (functional probe)" if args.probe else " (auth only)"))
        return 0 if usable == len(recs) else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
