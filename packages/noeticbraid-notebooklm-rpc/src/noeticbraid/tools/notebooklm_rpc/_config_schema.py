from __future__ import annotations

from jsonschema import Draft7Validator

from ._errors import NotebookLMPoolStateError

POOL_CONFIG_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "accounts"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": 1},
        "accounts": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["account_id", "storage_state_path"],
                "additionalProperties": False,
                "properties": {
                    "account_id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9_-]{0,63}$"},
                    "storage_state_path": {"type": "string", "minLength": 1},
                    "daily_quota": {"type": "integer", "minimum": 1, "default": 100},
                    "quota_reset_tz": {"type": "string", "default": "UTC"},
                    "label": {"type": ["string", "null"], "default": None},
                },
            },
            "uniqueItems": True,
        },
        "selection_policy": {
            "type": "string",
            "enum": ["least_recent_success"],
            "default": "least_recent_success",
        },
        "cool_down_seconds": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "rate_limited": {"type": "integer", "minimum": 1, "default": 3600},
                "login_required": {"type": "integer", "minimum": 1, "default": 43200},
                "captcha": {"type": "integer", "minimum": 1, "default": 86400},
                "server_error_streak": {"type": "integer", "minimum": 1, "default": 1800},
            },
            "default": {},
        },
    },
}

POOL_STATE_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["version", "updated_at", "accounts"],
    "additionalProperties": False,
    "properties": {
        "version": {"const": 1},
        "updated_at": {"type": "string", "format": "date-time"},
        "accounts": {
            "type": "object",
            "patternProperties": {
                "^[a-z0-9][a-z0-9_-]{0,63}$": {
                    "type": "object",
                    "required": ["used_today"],
                    "additionalProperties": False,
                    "properties": {
                        "used_today": {"type": "integer", "minimum": 0},
                        "quota_reset_at": {"type": ["string", "null"], "format": "date-time"},
                        "last_429_at": {"type": ["string", "null"], "format": "date-time"},
                        "last_captcha_at": {"type": ["string", "null"], "format": "date-time"},
                        "last_login_required_at": {"type": ["string", "null"], "format": "date-time"},
                        "cool_down_until": {"type": ["string", "null"], "format": "date-time"},
                        "last_success_at": {"type": ["string", "null"], "format": "date-time"},
                        "consecutive_failures": {"type": "integer", "minimum": 0},
                    },
                },
            },
            "additionalProperties": False,
        },
    },
}


def _validate(schema: dict, doc: dict, label: str) -> None:
    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(doc), key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise NotebookLMPoolStateError(f"invalid {label}: {path}: {first.message}")


def validate_pool_config(doc: dict) -> None:
    """Raise NotebookLMPoolStateError on invalid; use jsonschema.Draft7Validator."""

    _validate(POOL_CONFIG_SCHEMA, doc, "pool config")


def validate_pool_state(doc: dict) -> None:
    """Same, for state.json."""

    _validate(POOL_STATE_SCHEMA, doc, "pool state")
