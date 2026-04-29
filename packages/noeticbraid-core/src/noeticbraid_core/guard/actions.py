"""16 actions covered by ModeEnforcer (Phase 1.1)."""

from __future__ import annotations

from enum import Enum


class Action(str, Enum):
    """All actions ModeEnforcer can decide on.

    See docs/contracts/phase1_1_api_contract.md §7 for the three RED LINE
    actions (9, 15, 16). They are permanently denied across all modes.
    """

    # 1-8: read/write local + state + ledger + source_index + user raw read
    READ_LOCAL_FILE = "read_local_file"
    WRITE_LOCAL_FILE_NONDESTRUCTIVE = "write_local_file_nondestructive"
    DELETE_LOCAL_FILE = "delete_local_file"
    READ_STATE = "read_state"
    APPEND_RUN_LEDGER = "append_run_ledger"
    READ_SOURCE_INDEX = "read_source_index"
    WRITE_SOURCE_INDEX = "write_source_index"
    READ_USER_RAW_VAULT = "read_user_raw_vault"

    # 9 RED LINE: write user raw is permanently denied (api_contract §7 #1)
    WRITE_USER_RAW_VAULT = "write_user_raw_vault"

    # 10-14: external invocations
    INVOKE_LLM_CODE_CLI = "invoke_llm_code_cli"
    INVOKE_LLM_WEB = "invoke_llm_web"
    INVOKE_SUBPROCESS = "invoke_subprocess"
    EXTERNAL_WRITE = "external_write"
    USE_CREDENTIAL = "use_credential"

    # 15 RED LINE: rewrite existing SideNote permanently denied (api_contract §7 #2)
    REWRITE_SIDENOTE_EXISTING = "rewrite_sidenote_existing"

    # 16 RED LINE: cross-account transfer permanently denied (api_contract §7 #3)
    CROSS_ACCOUNT_TRANSFER = "cross_account_transfer"
