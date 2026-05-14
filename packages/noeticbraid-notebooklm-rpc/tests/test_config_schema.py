from __future__ import annotations

import pytest

from conftest import load_fixture
from noeticbraid.tools.notebooklm_rpc import NotebookLMPoolStateError
from noeticbraid.tools.notebooklm_rpc._config_schema import validate_pool_config, validate_pool_state


def test_pool_config_schema_validates_fixtures(fixtures_dir):
    validate_pool_config(load_fixture(fixtures_dir, "pool_config_single.json"))
    validate_pool_config(load_fixture(fixtures_dir, "pool_config_multi.json"))


def test_pool_state_schema_validates_fixtures(fixtures_dir):
    validate_pool_state(load_fixture(fixtures_dir, "pool_state_warm.json"))
    validate_pool_state(load_fixture(fixtures_dir, "pool_state_cooldown.json"))


def test_invalid_account_id_pattern_fails(fixtures_dir):
    doc = load_fixture(fixtures_dir, "pool_config_single.json")
    doc["accounts"][0]["account_id"] = "UPPER"

    with pytest.raises(NotebookLMPoolStateError):
        validate_pool_config(doc)


def test_pool_config_session_index_rejected(fixtures_dir):
    doc = load_fixture(fixtures_dir, "pool_config_single.json")
    doc["accounts"][0]["session_index"] = 1

    with pytest.raises(NotebookLMPoolStateError):
        validate_pool_config(doc)
