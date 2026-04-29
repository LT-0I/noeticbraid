"""Decision types returned by ModeEnforcer.check()."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class DecisionVerdict(str, Enum):
    """Allowed verdict values for guard decisions."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class Decision:
    """A decision emitted by ModeEnforcer.check().

    Attributes:
        verdict: ALLOW / DENY / REQUIRE_APPROVAL.
        reason: Non-empty explanation string.
        approval_request_id: uuid string, only present when verdict ==
            REQUIRE_APPROVAL; None otherwise.
    """

    verdict: DecisionVerdict
    reason: str
    approval_request_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, DecisionVerdict):
            raise TypeError("Decision.verdict must be a DecisionVerdict")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Decision.reason must be a non-empty string")
        if self.approval_request_id is not None and not isinstance(self.approval_request_id, str):
            raise TypeError("Decision.approval_request_id must be a string or None")
        if self.verdict == DecisionVerdict.REQUIRE_APPROVAL and not self.approval_request_id:
            raise ValueError(
                "Decision.approval_request_id must be set when verdict == REQUIRE_APPROVAL"
            )
        if self.verdict != DecisionVerdict.REQUIRE_APPROVAL and self.approval_request_id is not None:
            raise ValueError(
                "Decision.approval_request_id must be None when verdict != REQUIRE_APPROVAL"
            )
