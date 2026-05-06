# SPDX-License-Identifier: Apache-2.0
"""NoeticBraid SP-C2 Browser & CLI Runtime public API."""

from __future__ import annotations

from typing import Any, Callable

from noeticbraid_runtime.browser.cdp_session import CdpSession
from noeticbraid_runtime.browser.playwright_launcher import BrowserProcess, launch_browser
from noeticbraid_runtime.browser.session import BrowserSession
from noeticbraid_runtime.cli.sandbox import CLISandbox
from noeticbraid_runtime.run_record import runtime_artifact_refs, runtime_event_payload

SessionFactory = Callable[..., BrowserSession]


def get_session(
    tab_id: str | None = None,
    *,
    cdp_port: int = 9222,
    timeout_s: int = 10,
    session_factory: SessionFactory | None = None,
) -> BrowserSession:
    """Return a CDP BrowserSession.

    Semantics required by the C2 review:
    - `tab_id` set: attach to that target id or fail.
    - `tab_id=None`: attach to the first page target if present; otherwise create an
      `about:blank` target through the local CDP `/json/new` endpoint.
    - `session_factory` is a test/integration hook and receives the normalized args.
    """

    if cdp_port <= 0:
        raise ValueError("cdp_port must be positive")
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    factory = session_factory or CdpSession.from_cdp_port
    return factory(tab_id=tab_id, cdp_port=cdp_port, timeout_s=timeout_s)


__all__ = ["BrowserProcess", "BrowserSession", "CLISandbox", "get_session", "launch_browser", "runtime_artifact_refs", "runtime_event_payload"]
