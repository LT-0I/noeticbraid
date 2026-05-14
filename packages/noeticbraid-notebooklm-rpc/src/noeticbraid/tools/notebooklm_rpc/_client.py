from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Awaitable, Callable, Optional, TypeVar
import inspect

import notebooklm

from ._errors import NotebookLMPoolStateError
from ._pool import NotebookLMAccountPool
from ._runlog import emit_runlog_event

T = TypeVar("T")


def _verify_upstream_compat() -> None:
    """Module-load drift check. Called automatically at import time from
    `noeticbraid.tools.notebooklm_rpc._client` module body.

    Raises `NotebookLMPoolStateError(f"upstream API drift: {check_name}")` if
    upstream signatures drift from v0.4.1. First failed check wins.

    Checks (10 total):
        - notebooklm.NotebookLMClient.from_storage is a coroutine function
        - hasattr(notebooklm.NotebookLMClient, "__aexit__")
        - hasattr(notebooklm, "AuthError")
        - hasattr(notebooklm, "RateLimitError")
        - hasattr(notebooklm, "ServerError")
        - hasattr(notebooklm, "NotebookNotFoundError")
        - hasattr(notebooklm, "SourceNotFoundError")
        - hasattr(notebooklm, "NotebookLMError")
        - hasattr(notebooklm, "AuthTokens")
        - inspect.iscoroutinefunction(notebooklm.AuthTokens.from_storage)

    Testing posture (NORMATIVE): tests verify drift detection by:
        1. importing `noeticbraid.tools.notebooklm_rpc` once normally (module
           load → _verify_upstream_compat passes against real upstream)
        2. `monkeypatch.setattr(notebooklm, "RateLimitError", ...)` (or delattr)
           to simulate drift
        3. directly call `_verify_upstream_compat()` again and assert it raises
        4. monkeypatch teardown restores upstream

    DO NOT attempt to "monkeypatch _verify_upstream_compat to no-op BEFORE import"
    — that path is impossible because the function is defined and called in the
    same module body.
    """

    checks: tuple[tuple[str, Callable[[], bool]], ...] = (
        (
            "NotebookLMClient.from_storage",
            lambda: inspect.iscoroutinefunction(
                getattr(getattr(notebooklm, "NotebookLMClient", None), "from_storage", None)
            ),
        ),
        (
            "NotebookLMClient.__aexit__",
            lambda: hasattr(getattr(notebooklm, "NotebookLMClient", None), "__aexit__"),
        ),
        ("AuthError", lambda: hasattr(notebooklm, "AuthError")),
        ("RateLimitError", lambda: hasattr(notebooklm, "RateLimitError")),
        ("ServerError", lambda: hasattr(notebooklm, "ServerError")),
        ("NotebookNotFoundError", lambda: hasattr(notebooklm, "NotebookNotFoundError")),
        ("SourceNotFoundError", lambda: hasattr(notebooklm, "SourceNotFoundError")),
        ("NotebookLMError", lambda: hasattr(notebooklm, "NotebookLMError")),
        ("AuthTokens", lambda: hasattr(notebooklm, "AuthTokens")),
        (
            "AuthTokens.from_storage",
            lambda: inspect.iscoroutinefunction(
                getattr(getattr(notebooklm, "AuthTokens", None), "from_storage", None)
            ),
        ),
    )
    for check_name, check in checks:
        try:
            passed = check()
        except AttributeError:
            passed = False
        if not passed:
            raise NotebookLMPoolStateError(f"upstream API drift: {check_name}")


_verify_upstream_compat()  # called once at module load, before upstream name alias binding


_ROTATION_TRIGGER_TYPES: tuple[type[BaseException], ...] = (
    notebooklm.AuthError,
    notebooklm.RateLimitError,
    notebooklm.ServerError,
)
# 注：捕获 captcha substring / quota exhausted 由 pool.mark_failure 内部判断；
# _is_rotation_trigger 函数同时调用 mark_failure 的 cool-down decision 路径并询问
# state.cool_down_until 是否被设置过。详见 §File 4 错误映射表。


def _is_rotation_trigger(error: BaseException, *, account_just_marked: bool) -> bool:
    """Determine if the error type warrants picking a new account.
    Pool.mark_failure has already been called; account_just_marked indicates
    whether mark_failure set cool_down_until (i.e., it's a "rotation-worthy" error).
    Returns True iff:
        isinstance(error, _ROTATION_TRIGGER_TYPES) OR
        ("captcha" substring in str(error).lower()) OR
        account_just_marked is True (mark_failure applied cool_down).
    Does NOT trigger on NotebookNotFoundError / SourceNotFoundError / generic
    NotebookLMError / non-notebooklm errors.
    """

    if isinstance(error, (notebooklm.NotebookNotFoundError, notebooklm.SourceNotFoundError)):
        return False
    return (
        isinstance(error, _ROTATION_TRIGGER_TYPES)
        or "captcha" in str(error).lower()
        or account_just_marked is True
    )


@asynccontextmanager
async def account_op(
    pool: NotebookLMAccountPool,
    *,
    timeout: float = 30.0,
) -> AsyncIterator[tuple[notebooklm.NotebookLMClient, str]]:
    """Pick one account, open upstream client via `async with`, yield to caller body.

    Semantics (NO retry; one-shot)：
        spec = pool.pick()
            # raises NotebookLMAccountUnavailableError if pool empty (propagates).
            # pool.pick() already emits "pool.pick" runlog (per §File 5).

        try:
            client = await notebooklm.NotebookLMClient.from_storage(
                path=spec.storage_state_path,
                timeout=timeout,
            )
            async with client:
                yield (client, spec.account_id)
            # __aexit__ has completed without raising at this point.
        except BaseException as exc:
            # Covers from_storage failures, __aenter__ failures, body raises,
            # AND __aexit__ raises (since `async with` propagates them).
            pool.mark_failure(spec.account_id, exc)
            raise
        else:
            # mark_success only when from_storage + __aenter__ + body + __aexit__
            # all succeeded — strictly outside `async with`.
            pool.mark_success(spec.account_id)

    Usage:
        async with account_op(pool) as (client, account_id):
            notebooks = await client.notebooks.list()
        # On exit normal: pool.mark_success + upstream close
        # On exit exception: pool.mark_failure + upstream close + re-raise

    NO automatic rotation. If caller wants rotation on RateLimitError, wrap with
    `run_with_pool(pool, lambda c: c.notebooks.list())` instead.

    THREAD-SAFETY: pool internal state mutations are lock-protected (§File 5).
    Multiple concurrent `account_op` callers in the same event loop are safe.
    """

    spec = pool.pick()
    try:
        client = await notebooklm.NotebookLMClient.from_storage(
            path=spec.storage_state_path,
            timeout=timeout,
        )
        async with client:
            yield (client, spec.account_id)
    except BaseException as exc:
        pool.mark_failure(spec.account_id, exc)
        raise
    else:
        pool.mark_success(spec.account_id)


async def run_with_pool(
    pool: NotebookLMAccountPool,
    op_fn: Callable[[notebooklm.NotebookLMClient], Awaitable[T]],
    *,
    timeout: float = 30.0,
    max_rotations: Optional[int] = None,
) -> T:
    """Pick an account, open upstream client, call `await op_fn(client)`; on
    rotation-triggering failure, mark + close + pick again; up to max_rotations
    additional attempts.

    `op_fn` MUST be idempotent: it may be invoked multiple times against
    different accounts. Side effects (e.g., create_notebook) on a failed attempt
    persist on the failed account. Caller is responsible for designing op_fn
    to tolerate this (e.g., use idempotent ops, or do explicit reconciliation).

    Args:
        pool: NotebookLMAccountPool instance
        op_fn: async callable taking one upstream NotebookLMClient
        timeout: per-attempt upstream HTTP timeout
        max_rotations: max additional attempts after initial failure.
                       Default = pool.account_count - 1 (evaluated at call time).
                       max_rotations=0 means: try once, no retry.

    Returns:
        Result of `await op_fn(client)` on the successful attempt.

    Raises:
        - The last attempt's exception if all attempts failed
        - NotebookLMAccountUnavailableError if pool exhausted during retries
        - Non-rotation-triggering exceptions (e.g., NotebookNotFoundError)
          are not retried; first raise wins.

    Semantics (precise)：
        rotations = 0
        max_r = max_rotations if max_rotations is not None else pool.account_count - 1
        tried_account_ids: set[str] = set()

        while True:
            spec = pool.pick(exclude=frozenset(tried_account_ids))
                # raises NotebookLMAccountUnavailableError if all candidates
                # are excluded or otherwise ineligible — propagates as final
                # outcome when retry budget reaches the natural pool limit.
            tried_account_ids.add(spec.account_id)

            try:
                client = await notebooklm.NotebookLMClient.from_storage(
                    path=spec.storage_state_path,
                    timeout=timeout,
                )
                async with client:
                    result = await op_fn(client)
                # __aexit__ completed normally
            except BaseException as exc:
                # Covers from_storage, __aenter__, op_fn body, __aexit__ raises.
                # mark_failure() returns cool_down_applied atomically (computed
                # inside its lock) — this is the authoritative rotation signal
                # for non-typed errors (race-free vs rev4's pre/post snapshot).
                cool_down_applied = pool.mark_failure(spec.account_id, exc)

                if not _is_rotation_trigger(exc, account_just_marked=cool_down_applied):
                    raise
                if rotations >= max_r:
                    raise
                rotations += 1
                emit_runlog_event(
                    "pool.rotation",
                    {"from_account_id": spec.account_id,
                     "error_class": type(exc).__name__,
                     "rotation_index": rotations,
                     "max_rotations": max_r,
                     "tried_account_ids": sorted(tried_account_ids)},
                )
                continue

            # Strictly outside both try and `async with` — only on the cleanest
            # success path. __aexit__ has completed normally.
            pool.mark_success(spec.account_id)
            return result
    """

    rotations = 0
    max_r = max_rotations if max_rotations is not None else pool.account_count - 1
    tried_account_ids: set[str] = set()

    while True:
        spec = pool.pick(exclude=frozenset(tried_account_ids))
        tried_account_ids.add(spec.account_id)

        try:
            client = await notebooklm.NotebookLMClient.from_storage(
                path=spec.storage_state_path,
                timeout=timeout,
            )
            async with client:
                result = await op_fn(client)
        except BaseException as exc:
            cool_down_applied = pool.mark_failure(spec.account_id, exc)
            if not _is_rotation_trigger(exc, account_just_marked=cool_down_applied):
                raise
            if rotations >= max_r:
                raise
            rotations += 1
            emit_runlog_event(
                "pool.rotation",
                {
                    "from_account_id": spec.account_id,
                    "error_class": type(exc).__name__,
                    "rotation_index": rotations,
                    "max_rotations": max_r,
                    "tried_account_ids": sorted(tried_account_ids),
                },
            )
            continue

        pool.mark_success(spec.account_id)
        return result
