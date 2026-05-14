from __future__ import annotations

import asyncio
import threading

import notebooklm

from conftest import pool_from_config_doc, read_json
from noeticbraid.tools.notebooklm_rpc import NotebookLMAccountUnavailableError
from noeticbraid.tools.notebooklm_rpc._config_schema import validate_pool_state


def _two_account_config(quota: int) -> dict:
    return {
        "version": 1,
        "accounts": [
            {"account_id": "acct-a", "storage_state_path": "/tmp/a.json", "daily_quota": quota},
            {"account_id": "acct-b", "storage_state_path": "/tmp/b.json", "daily_quota": quota},
        ],
    }


def test_threaded_picks_distinct_no_race(tmp_path, fake_clock):
    pool = pool_from_config_doc(_two_account_config(1000), tmp_path, fake_clock)

    def worker():
        for _ in range(50):
            spec = pool.pick()
            pool.mark_success(spec.account_id)

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    state = read_json(tmp_path / "pool-state.json")["accounts"]
    assert sum(account["used_today"] for account in state.values()) == 100


def test_serial_quota_exact(tmp_path, fake_clock):
    pool = pool_from_config_doc(_two_account_config(10), tmp_path, fake_clock)
    successes = 0

    for _ in range(25):
        try:
            spec = pool.pick()
        except NotebookLMAccountUnavailableError:
            break
        pool.mark_success(spec.account_id)
        successes += 1

    assert successes == 20
    state = read_json(tmp_path / "pool-state.json")["accounts"]
    assert sum(account["used_today"] for account in state.values()) == 20


def test_concurrent_quota_best_effort_bound(tmp_path, fake_clock):
    concurrency = 8
    pool = pool_from_config_doc(_two_account_config(10), tmp_path, fake_clock)
    marked = 0
    marked_lock = threading.Lock()

    def worker():
        nonlocal marked
        while True:
            try:
                spec = pool.pick()
            except NotebookLMAccountUnavailableError:
                return
            pool.mark_success(spec.account_id)
            with marked_lock:
                marked += 1

    threads = [threading.Thread(target=worker) for _ in range(concurrency)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert marked <= 20 + (concurrency - 1)
    validate_pool_state(read_json(tmp_path / "pool-state.json"))


def test_threaded_mark_failure_no_state_corruption(tmp_path, fake_clock):
    pool = pool_from_config_doc(_two_account_config(1000), tmp_path, fake_clock)

    def worker(account_id: str):
        for index in range(100):
            if index % 2:
                pool.mark_success(account_id)
            else:
                pool.mark_failure(account_id, notebooklm.RateLimitError("rate"))
            if index % 10 == 0:
                validate_pool_state(read_json(tmp_path / "pool-state.json"))

    threads = [threading.Thread(target=worker, args=("acct-a",)), threading.Thread(target=worker, args=("acct-b",)), threading.Thread(target=worker, args=("acct-a",))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    validate_pool_state(read_json(tmp_path / "pool-state.json"))


async def test_asyncio_gather_no_deadlock(tmp_path, fake_clock):
    pool = pool_from_config_doc(_two_account_config(100), tmp_path, fake_clock)

    async def worker():
        spec = pool.pick()
        pool.mark_success(spec.account_id)

    await asyncio.wait_for(asyncio.gather(*(worker() for _ in range(4))), timeout=2)
