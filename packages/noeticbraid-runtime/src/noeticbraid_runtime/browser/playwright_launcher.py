# SPDX-License-Identifier: Apache-2.0
"""Playwright-backed Chrome process launcher."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from noeticbraid_runtime._proxy import build_proxy_args

LauncherCallable = Callable[..., Any]


class BrowserLaunchError(Exception):
    """Raised when browser launch cannot be performed."""


@dataclass(frozen=True)
class BrowserProcess:
    """Handle returned by `launch_browser`."""

    profile_dir: Path
    cdp_port: int
    proxy_url: str | None
    headless: bool
    handle: Any
    args: tuple[str, ...]

    def close(self) -> None:
        """Close the underlying Playwright context/process if it exposes close()."""

        close = getattr(self.handle, "close", None)
        if callable(close):
            close()


def build_chrome_args(
    *,
    profile_dir: str | Path,
    proxy_url: str | None = None,
    cdp_port: int = 9222,
    headless: bool = False,
) -> list[str]:
    """Build deterministic Chrome launch args."""

    profile_path = Path(profile_dir).resolve()
    args = [
        f"--user-data-dir={profile_path}",
        f"--remote-debugging-port={cdp_port}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        args.append("--headless=new")
    else:
        args.append("--start-maximized")
    args.extend(build_proxy_args(proxy_url))
    return args


def launch_browser(
    profile_dir: str,
    *,
    proxy_url: str | None = None,
    cdp_port: int = 9222,
    headless: bool = False,
    launcher: LauncherCallable | None = None,
) -> BrowserProcess:
    """Launch a persistent Chrome context and expose the configured CDP port.

    Tests and upper orchestration may pass `launcher` to avoid importing Playwright.
    Without `launcher`, `playwright.sync_api` is imported lazily and must be installed
    through the `browser` optional extra.
    """

    if cdp_port <= 0:
        raise ValueError("cdp_port must be positive")
    profile_path = Path(profile_dir).resolve()
    profile_path.mkdir(parents=True, exist_ok=True)
    args = build_chrome_args(profile_dir=profile_path, proxy_url=proxy_url, cdp_port=cdp_port, headless=headless)
    if launcher is None:
        handle = _launch_with_playwright(profile_dir=profile_path, args=args, headless=headless)
    else:
        handle = launcher(profile_dir=profile_path, args=args, headless=headless)
    return BrowserProcess(
        profile_dir=profile_path,
        cdp_port=cdp_port,
        proxy_url=proxy_url,
        headless=headless,
        handle=handle,
        args=tuple(args),
    )


def _launch_with_playwright(*, profile_dir: Path, args: list[str], headless: bool) -> Any:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except Exception as exc:
        raise BrowserLaunchError("playwright is required for launch_browser without an injected launcher") from exc
    manager = sync_playwright().start()
    filtered_args = [arg for arg in args if not arg.startswith("--user-data-dir=")]
    try:
        context = manager.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=headless,
            args=filtered_args,
        )
    except Exception:
        manager.stop()
        raise
    return _PlaywrightHandle(manager=manager, context=context)


@dataclass
class _PlaywrightHandle:
    manager: Any
    context: Any

    def close(self) -> None:
        try:
            self.context.close()
        finally:
            self.manager.stop()


__all__ = ["BrowserLaunchError", "BrowserProcess", "build_chrome_args", "launch_browser"]
