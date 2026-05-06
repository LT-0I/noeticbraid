# SPDX-License-Identifier: Apache-2.0
"""Chrome DevTools Protocol BrowserSession implementation."""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path
from typing import Any, Protocol


class CdpSessionError(Exception):
    """Raised when a CDP operation fails."""


class CdpTransport(Protocol):
    """Small transport protocol for tests and websocket-client implementation."""

    def call(self, method: str, params: dict[str, Any] | None = None, timeout_s: float | None = None) -> dict[str, Any]: ...

    def close(self) -> None: ...


class WebSocketCdpTransport:
    """websocket-client based CDP transport loaded only when used."""

    def __init__(self, cdp_url: str, *, timeout_s: float = 10) -> None:
        try:
            import websocket  # type: ignore[import-not-found]
        except Exception as exc:
            raise CdpSessionError("websocket-client is required for live CDP sessions") from exc
        self._ws = websocket.create_connection(cdp_url, timeout=timeout_s)
        self._next_id = 1

    def call(self, method: str, params: dict[str, Any] | None = None, timeout_s: float | None = None) -> dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        if timeout_s is not None:
            self._ws.settimeout(timeout_s)
        self._ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            raw = self._ws.recv()
            payload = json.loads(raw)
            if payload.get("id") != msg_id:
                continue
            if "error" in payload:
                raise CdpSessionError(str(payload["error"]))
            return payload.get("result", {})

    def close(self) -> None:
        self._ws.close()


class CdpSession:
    """CDP-backed implementation of the BrowserSession protocol."""

    def __init__(self, *, tab_id: str, cdp_url: str, transport: CdpTransport | None = None, timeout_s: float = 10) -> None:
        self.tab_id = tab_id
        self.cdp_url = cdp_url
        self._transport = transport or WebSocketCdpTransport(cdp_url, timeout_s=timeout_s)

    @classmethod
    def from_cdp_port(
        cls,
        *,
        tab_id: str | None = None,
        cdp_port: int = 9222,
        timeout_s: int = 10,
    ) -> "CdpSession":
        """Attach to an existing tab or create a new blank tab when none exists.

        `tab_id=None` means: attach to the first page target if present, otherwise ask
        Chrome's `/json/new` endpoint to create an `about:blank` tab.
        """

        target = _resolve_target(tab_id=tab_id, cdp_port=cdp_port, timeout_s=timeout_s)
        return cls(tab_id=target["id"], cdp_url=target["webSocketDebuggerUrl"], timeout_s=timeout_s)

    def navigate(self, url: str, timeout_s: int = 30) -> None:
        self._transport.call("Page.navigate", {"url": url}, timeout_s=timeout_s)

    def eval(self, expression: str, await_promise: bool = True, timeout_s: int = 30) -> Any:
        result = self._transport.call(
            "Runtime.evaluate",
            {"expression": expression, "awaitPromise": await_promise, "returnByValue": True},
            timeout_s=timeout_s,
        )
        value_holder = result.get("result", result)
        if isinstance(value_holder, dict):
            if "value" in value_holder:
                return value_holder["value"]
            if "description" in value_holder:
                return value_holder["description"]
        return value_holder

    def click(self, x: float, y: float, timeout_s: int = 30) -> None:
        params = {"x": x, "y": y, "button": "left", "clickCount": 1}
        self._transport.call("Input.dispatchMouseEvent", params | {"type": "mousePressed"}, timeout_s=timeout_s)
        self._transport.call("Input.dispatchMouseEvent", params | {"type": "mouseReleased"}, timeout_s=timeout_s)

    def type_text(self, text: str, timeout_s: int = 30) -> None:
        self._transport.call("Input.insertText", {"text": text}, timeout_s=timeout_s)

    def screenshot(self, save_to: str, timeout_s: int = 30) -> int:
        result = self._transport.call("Page.captureScreenshot", {"format": "png", "fromSurface": True}, timeout_s=timeout_s)
        data = result.get("data")
        if not isinstance(data, str):
            raise CdpSessionError("Page.captureScreenshot returned no data")
        raw = base64.b64decode(data)
        path = Path(save_to)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return len(raw)

    def close(self) -> None:
        self._transport.close()


def _resolve_target(*, tab_id: str | None, cdp_port: int, timeout_s: int) -> dict[str, Any]:
    targets = _read_json(f"http://127.0.0.1:{cdp_port}/json/list", timeout_s=timeout_s)
    if not isinstance(targets, list):
        raise CdpSessionError("CDP /json/list returned invalid payload")
    if tab_id:
        for target in targets:
            if target.get("id") == tab_id:
                return _validate_target(target)
        raise CdpSessionError(f"CDP tab id not found: {tab_id}")
    for target in targets:
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
            return _validate_target(target)
    created = _read_json(f"http://127.0.0.1:{cdp_port}/json/new?about:blank", timeout_s=timeout_s, method="PUT")
    return _validate_target(created)


def _validate_target(target: Any) -> dict[str, Any]:
    if not isinstance(target, dict) or not isinstance(target.get("id"), str) or not isinstance(target.get("webSocketDebuggerUrl"), str):
        raise CdpSessionError("CDP target missing id or webSocketDebuggerUrl")
    return target


def _read_json(url: str, *, timeout_s: int, method: str = "GET") -> Any:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout_s) as response:  # noqa: S310 - localhost CDP endpoint only
        return json.loads(response.read().decode("utf-8"))


__all__ = ["CdpSession", "CdpSessionError", "CdpTransport", "WebSocketCdpTransport"]
