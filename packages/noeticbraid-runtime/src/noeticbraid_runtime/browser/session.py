# SPDX-License-Identifier: Apache-2.0
"""Browser session protocol consumed by upper SP modules."""

from __future__ import annotations

from typing import Any, Protocol


class BrowserSession(Protocol):
    """Minimal browser automation surface for H/B/D/E modules.

    Upper layers depend on this protocol instead of Playwright/CDP details.
    """

    tab_id: str
    cdp_url: str

    def navigate(self, url: str, timeout_s: int = 30) -> None: ...

    def eval(self, expression: str, await_promise: bool = True, timeout_s: int = 30) -> Any: ...

    def click(self, x: float, y: float, timeout_s: int = 30) -> None: ...

    def type_text(self, text: str, timeout_s: int = 30) -> None: ...

    def screenshot(self, save_to: str, timeout_s: int = 30) -> int: ...

    def close(self) -> None: ...


__all__ = ["BrowserSession"]
