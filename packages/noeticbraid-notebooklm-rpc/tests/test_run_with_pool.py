from __future__ import annotations

import inspect

import notebooklm
import pytest

from conftest import FakeNotebookLMClient, load_fixture, pool_from_config_doc, read_runlog
from noeticbraid.tools.notebooklm_rpc import NotebookLMAccountUnavailableError, run_with_pool
from noeticbraid.tools.notebooklm_rpc._client import run_with_pool as run_with_pool_impl


def _multi_pool(fixtures_dir, tmp_path, fake_clock, *, state_doc=None, count=2):
    config = load_fixture(fixtures_dir, "pool_config_multi.json")
    config["accounts"] = config["accounts"][:count]
    if state_doc is not None:
        state_doc = {**state_doc, "accounts": {k: v for k, v in state_doc["accounts"].items() if k in {a["account_id"] for a in config["accounts"]}}}
    return pool_from_config_doc(config, tmp_path, fake_clock, state_doc=state_doc)


async def test_run_with_pool_success_first_try(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    controller = patch_from_storage(FakeNotebookLMClient(path="/tmp/test-alice-storage.json"))
    failure_calls = []
    original_failure = pool.mark_failure

    def mark_failure(account_id, error):
        failure_calls.append((account_id, error))
        return original_failure(account_id, error)

    pool.mark_failure = mark_failure

    result = await run_with_pool(pool, lambda client: client.notebooks.list())

    assert result
    assert len(controller.calls) == 1
    assert failure_calls == []
    assert sum(account["used_today"] for account in pool._state_doc()["accounts"].values()) == 1


async def test_run_with_pool_retries_on_rate_limit(fixtures_dir, tmp_path, fake_clock, patch_from_storage, isolated_runlog):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    patch_from_storage(FakeNotebookLMClient(path="/tmp/a.json"), FakeNotebookLMClient(path="/tmp/b.json"))
    attempts = 0

    async def op(_client):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise notebooklm.RateLimitError("rate")
        return "ok"

    assert await run_with_pool(pool, op) == "ok"
    assert attempts == 2
    assert [event["kind"] for event in read_runlog(isolated_runlog)].count("pool.rotation") == 1


async def test_run_with_pool_does_not_retry_on_not_found(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    controller = patch_from_storage(FakeNotebookLMClient(path="/tmp/a.json"), FakeNotebookLMClient(path="/tmp/b.json"))

    async def op(_client):
        raise notebooklm.NotebookNotFoundError("nb1")

    with pytest.raises(notebooklm.NotebookNotFoundError):
        await run_with_pool(pool, op)

    assert len(controller.calls) == 1


async def test_run_with_pool_max_rotations_zero(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    controller = patch_from_storage(FakeNotebookLMClient(path="/tmp/a.json"), FakeNotebookLMClient(path="/tmp/b.json"))

    async def op(_client):
        raise notebooklm.RateLimitError("rate")

    with pytest.raises(notebooklm.RateLimitError):
        await run_with_pool(pool, op, max_rotations=0)

    assert len(controller.calls) == 1


async def test_run_with_pool_exhausts_via_exclude(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    controller = patch_from_storage(FakeNotebookLMClient(path="/tmp/a.json"), FakeNotebookLMClient(path="/tmp/b.json"))

    async def op(_client):
        raise notebooklm.RateLimitError("rate")

    with pytest.raises(NotebookLMAccountUnavailableError) as exc_info:
        await run_with_pool(pool, op, max_rotations=10)

    assert exc_info.value.reason == "all_excluded"
    assert len(controller.calls) == 2


def test_run_with_pool_idempotency_contract_documented():
    assert "idempotent" in inspect.getdoc(run_with_pool_impl)


async def test_run_with_pool_excludes_tried_accounts_in_order(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(
        fixtures_dir,
        tmp_path,
        fake_clock,
        state_doc=load_fixture(fixtures_dir, "pool_state_warm.json"),
        count=3,
    )
    patch_from_storage(
        FakeNotebookLMClient(path="/tmp/c.json"),
        FakeNotebookLMClient(path="/tmp/b.json"),
        FakeNotebookLMClient(path="/tmp/a.json"),
    )
    original_pick = pool.pick
    excludes = []
    picked = []

    def pick(*, exclude=frozenset()):
        excludes.append(frozenset(exclude))
        spec = original_pick(exclude=exclude)
        picked.append(spec.account_id)
        return spec

    pool.pick = pick

    async def op(_client):
        raise notebooklm.RateLimitError("rate")

    with pytest.raises(NotebookLMAccountUnavailableError) as exc_info:
        await run_with_pool(pool, op, max_rotations=10)

    assert exc_info.value.reason == "all_excluded"
    assert picked == ["test-carol", "test-bob", "test-alice"]
    assert excludes == [
        frozenset(),
        frozenset({"test-carol"}),
        frozenset({"test-carol", "test-bob"}),
        frozenset({"test-carol", "test-bob", "test-alice"}),
    ]


async def test_run_with_pool_from_storage_failure_marks_failure(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    controller = patch_from_storage(notebooklm.AuthError("login"), FakeNotebookLMClient(path="/tmp/b.json"))
    failure_calls = []
    original_failure = pool.mark_failure

    def mark_failure(account_id, error):
        failure_calls.append((account_id, error))
        return original_failure(account_id, error)

    pool.mark_failure = mark_failure

    async def op(_client):
        return "ok"

    assert await run_with_pool(pool, op) == "ok"
    assert len(controller.calls) == 2
    assert len(failure_calls) == 1
    assert isinstance(failure_calls[0][1], notebooklm.AuthError)


async def test_run_with_pool_aenter_failure_marks_failure(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = _multi_pool(fixtures_dir, tmp_path, fake_clock)
    first = FakeNotebookLMClient(path="/tmp/a.json", aenter_error=notebooklm.RateLimitError("rate"))
    second = FakeNotebookLMClient(path="/tmp/b.json")
    patch_from_storage(first, second)
    failure_calls = []
    original_failure = pool.mark_failure

    def mark_failure(account_id, error):
        failure_calls.append((account_id, error))
        return original_failure(account_id, error)

    pool.mark_failure = mark_failure

    async def op(_client):
        return "ok"

    assert await run_with_pool(pool, op) == "ok"
    assert len(failure_calls) == 1
    assert isinstance(failure_calls[0][1], notebooklm.RateLimitError)


async def test_run_with_pool_mark_success_only_after_aexit(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)
    patch_from_storage(FakeNotebookLMClient(path="/tmp/a.json", aexit_error=RuntimeError("aexit fail")))
    success_calls = []
    failure_calls = []
    original_failure = pool.mark_failure

    def mark_success(account_id):
        success_calls.append(account_id)

    def mark_failure(account_id, error):
        failure_calls.append((account_id, error))
        return original_failure(account_id, error)

    pool.mark_success = mark_success
    pool.mark_failure = mark_failure

    async def op(_client):
        return "body ok"

    with pytest.raises(RuntimeError, match="aexit fail"):
        await run_with_pool(pool, op)

    assert success_calls == []
    assert len(failure_calls) == 1
    assert isinstance(failure_calls[0][1], RuntimeError)
    assert str(failure_calls[0][1]) == "aexit fail"
