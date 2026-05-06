from __future__ import annotations

import sys
import types
from pathlib import Path

from noeticbraid_runtime import get_session, launch_browser
from noeticbraid_runtime.browser.playwright_launcher import BrowserProcess, _launch_with_playwright, build_chrome_args


def test_build_chrome_args_includes_profile_cdp_proxy_and_headful_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HELIXMIND_TRUST_FAKE_IP_RANGE", "198.18.0.0/15")

    args = build_chrome_args(profile_dir=tmp_path, proxy_url="http://127.0.0.1:8080", cdp_port=9333, headless=False)

    assert f"--user-data-dir={tmp_path}" in args
    assert "--remote-debugging-port=9333" in args
    assert "--proxy-server=http://127.0.0.1:8080" in args
    assert "--proxy-bypass-list=<local>;198.18.*.*" in args
    assert "--start-maximized" in args
    assert "--headless=new" not in args


def test_launch_browser_uses_injected_launcher_and_returns_process(tmp_path: Path) -> None:
    captured = {}

    def fake_launcher(*, profile_dir: Path, args: list[str], headless: bool):
        captured["profile_dir"] = profile_dir
        captured["args"] = args
        captured["headless"] = headless
        return {"handle": "fake"}

    process = launch_browser(str(tmp_path), proxy_url=None, cdp_port=9444, headless=True, launcher=fake_launcher)

    assert isinstance(process, BrowserProcess)
    assert process.cdp_port == 9444
    assert process.profile_dir == tmp_path
    assert captured["headless"] is True
    assert "--headless=new" in captured["args"]


def test_launch_with_playwright_filters_duplicate_user_data_dir(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeContext:
        def close(self) -> None:
            captured["closed"] = True

    class FakeChromium:
        def launch_persistent_context(self, **kwargs):
            captured.update(kwargs)
            return FakeContext()

    class FakeManager:
        chromium = FakeChromium()

        def stop(self) -> None:
            captured["stopped"] = True

    fake_module = types.SimpleNamespace(sync_playwright=lambda: types.SimpleNamespace(start=lambda: FakeManager()))
    monkeypatch.setitem(sys.modules, "playwright", types.SimpleNamespace(sync_api=fake_module))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_module)

    handle = _launch_with_playwright(
        profile_dir=tmp_path,
        args=[f"--user-data-dir={tmp_path}", "--remote-debugging-port=9444", "--start-maximized"],
        headless=False,
    )

    assert captured["user_data_dir"] == str(tmp_path)
    assert "--user-data-dir=" not in "\n".join(captured["args"])
    handle.close()
    assert captured["closed"] is True
    assert captured["stopped"] is True


def test_get_session_without_tab_id_creates_or_attaches_via_factory() -> None:
    calls = []

    def fake_factory(*, tab_id, cdp_port, timeout_s):
        calls.append({"tab_id": tab_id, "cdp_port": cdp_port, "timeout_s": timeout_s})
        return "session"

    assert get_session(None, cdp_port=9444, timeout_s=6, session_factory=fake_factory) == "session"
    assert calls == [{"tab_id": None, "cdp_port": 9444, "timeout_s": 6}]


def test_get_session_with_explicit_tab_id_propagates_to_factory() -> None:
    captured: dict[str, object] = {}

    def fake_factory(*, tab_id, cdp_port, timeout_s):
        captured["tab_id"] = tab_id
        captured["cdp_port"] = cdp_port
        captured["timeout_s"] = timeout_s
        return object()

    result = get_session("tab-X", cdp_port=9333, session_factory=fake_factory)

    assert result is not None
    assert captured == {"tab_id": "tab-X", "cdp_port": 9333, "timeout_s": 10}
