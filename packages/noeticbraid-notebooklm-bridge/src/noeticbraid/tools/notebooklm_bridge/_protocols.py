"""SP-C2 protocol boundaries consumed by SP-H."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BrowserSession(Protocol):
    """Current SP-C2-compatible browser session surface.

    SP-H receives this object from SP-C2. It never starts Chrome, opens CDP
    sockets, manages profiles, reads cookies, or logs in to Google. The current
    runtime exposes coordinate clicks and page evaluation, so SP-H resolves
    selectors through JavaScript and then calls ``click(x, y)``.
    """

    tab_id: str
    cdp_url: str

    def navigate(self, url: str, timeout_s: int = 30) -> None: ...

    def eval(self, expression: str, await_promise: bool = True, timeout_s: int = 30) -> Any: ...

    def click(self, x: float, y: float, timeout_s: int = 30) -> None: ...

    def type_text(self, text: str, timeout_s: int = 30) -> None: ...


class EventSink(Protocol):
    """Optional event sink shape that a BrowserSession may provide."""

    def emit_event(self, event: dict) -> None: ...
