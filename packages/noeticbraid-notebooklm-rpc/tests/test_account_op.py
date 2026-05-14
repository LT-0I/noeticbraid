from __future__ import annotations

import notebooklm
import pytest

from conftest import FakeNotebookLMClient, load_fixture, pool_from_config_doc, read_runlog
from noeticbraid.tools.notebooklm_rpc import account_op


async def test_account_op_marks_success_on_normal_exit(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)
    patch_from_storage(FakeNotebookLMClient(path="/tmp/test-alice-storage.json"))
    success_calls = []
    failure_calls = []
    original_success = pool.mark_success
    original_failure = pool.mark_failure

    def mark_success(account_id):
        success_calls.append(account_id)
        return original_success(account_id)

    def mark_failure(account_id, error):
        failure_calls.append((account_id, error))
        return original_failure(account_id, error)

    pool.mark_success = mark_success
    pool.mark_failure = mark_failure

    async with account_op(pool) as (client, account_id):
        assert account_id == "test-alice"
        assert await client.notebooks.list()

    assert success_calls == ["test-alice"]
    assert failure_calls == []


async def test_account_op_marks_failure_and_reraises_on_body_raise(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)
    patch_from_storage(FakeNotebookLMClient(path="/tmp/test-alice-storage.json"))
    failure_calls = []
    original_failure = pool.mark_failure

    def mark_failure(account_id, error):
        failure_calls.append((account_id, error))
        return original_failure(account_id, error)

    pool.mark_failure = mark_failure

    with pytest.raises(notebooklm.RateLimitError):
        async with account_op(pool):
            raise notebooklm.RateLimitError("rate")

    assert len(failure_calls) == 1
    assert failure_calls[0][0] == "test-alice"
    assert isinstance(failure_calls[0][1], notebooklm.RateLimitError)


async def test_account_op_emits_runlog_events(fixtures_dir, tmp_path, fake_clock, patch_from_storage, isolated_runlog):
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)
    patch_from_storage(FakeNotebookLMClient(path="/tmp/test-alice-storage.json"))

    async with account_op(pool):
        pass

    kinds = [event["kind"] for event in read_runlog(isolated_runlog)]
    assert "pool.pick" in kinds
    assert "pool.mark_success" in kinds


async def test_account_op_no_retry_on_not_found(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    state_doc = {
        "version": 1,
        "updated_at": fake_clock().isoformat(),
        "accounts": {
            "test-alice": {"used_today": 0, "quota_reset_at": "2026-05-15T00:00:00+00:00", "consecutive_failures": 0}
        },
    }
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock, state_doc=state_doc)
    controller = patch_from_storage(FakeNotebookLMClient(path="/tmp/test-alice-storage.json"))
    before = (tmp_path / "pool-state.json").read_text(encoding="utf-8")

    with pytest.raises(notebooklm.NotebookNotFoundError):
        async with account_op(pool):
            raise notebooklm.NotebookNotFoundError("nb1")

    assert len(controller.calls) == 1
    assert (tmp_path / "pool-state.json").read_text(encoding="utf-8") == before


async def test_account_op_uses_upstream_async_with(fixtures_dir, tmp_path, fake_clock, patch_from_storage):
    success_client = FakeNotebookLMClient(path="/tmp/test-alice-storage.json")
    pool = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path, fake_clock)
    patch_from_storage(success_client)

    async with account_op(pool):
        pass

    assert success_client.exited == 1

    failure_client = FakeNotebookLMClient(path="/tmp/test-alice-storage.json")
    pool2 = pool_from_config_doc(load_fixture(fixtures_dir, "pool_config_single.json"), tmp_path / "second", fake_clock)
    patch_from_storage(failure_client)

    with pytest.raises(notebooklm.RateLimitError):
        async with account_op(pool2):
            raise notebooklm.RateLimitError("rate")

    assert failure_client.exited == 1
    assert failure_client.exit_args is not None
    assert failure_client.exit_args[0] is notebooklm.RateLimitError
