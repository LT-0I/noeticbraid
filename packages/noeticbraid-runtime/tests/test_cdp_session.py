from __future__ import annotations

import base64
from pathlib import Path

from noeticbraid_runtime.browser.cdp_session import CdpSession


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def call(self, method: str, params: dict | None = None, timeout_s: float | None = None):
        payload = dict(params or {})
        payload["__timeout_s"] = timeout_s
        self.calls.append((method, payload))
        if method == "Runtime.evaluate":
            return {"result": {"value": 2}}
        if method == "Page.captureScreenshot":
            return {"data": base64.b64encode(b"png-bytes").decode("ascii")}
        return {}

    def close(self) -> None:
        self.closed = True


def test_cdp_session_implements_browser_session_methods(tmp_path: Path) -> None:
    transport = FakeTransport()
    session = CdpSession(tab_id="tab-1", cdp_url="ws://cdp", transport=transport)
    screenshot_path = tmp_path / "shot.png"

    session.navigate("https://example.com", timeout_s=7)
    result = session.eval("1 + 1", timeout_s=3)
    session.click(10, 20, timeout_s=2)
    session.type_text("hello", timeout_s=4)
    written = session.screenshot(str(screenshot_path), timeout_s=5)
    session.close()

    assert result == 2
    assert written == len(b"png-bytes")
    assert screenshot_path.read_bytes() == b"png-bytes"
    assert transport.closed is True
    methods = [method for method, _params in transport.calls]
    assert methods == [
        "Page.navigate",
        "Runtime.evaluate",
        "Input.dispatchMouseEvent",
        "Input.dispatchMouseEvent",
        "Input.insertText",
        "Page.captureScreenshot",
    ]
    assert transport.calls[0][1]["url"] == "https://example.com"
    assert transport.calls[1][1]["expression"] == "1 + 1"
    assert transport.calls[1][1]["awaitPromise"] is True
