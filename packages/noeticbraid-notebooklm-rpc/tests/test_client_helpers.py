from __future__ import annotations

import pytest
import notebooklm

from noeticbraid.tools.notebooklm_rpc import NotebookLMPoolStateError
from noeticbraid.tools.notebooklm_rpc._client import _verify_upstream_compat


def test_verify_upstream_compat_detects_drift_from_storage(monkeypatch):
    def not_async(*args, **kwargs):
        return None

    monkeypatch.setattr(notebooklm.NotebookLMClient, "from_storage", not_async)

    with pytest.raises(NotebookLMPoolStateError, match="NotebookLMClient.from_storage"):
        _verify_upstream_compat()


def test_verify_upstream_compat_detects_missing_exception_class(monkeypatch):
    monkeypatch.delattr(notebooklm, "RateLimitError", raising=True)

    with pytest.raises(NotebookLMPoolStateError, match="RateLimitError"):
        _verify_upstream_compat()
