# SPDX-License-Identifier: Apache-2.0
"""Proxy and TUN environment helpers for browser launch."""

from __future__ import annotations

import ipaddress
import os


def fake_ip_range_to_chrome_bypass(fake_ip_range: str | None) -> str | None:
    """Convert known TUN fake-IP CIDR values to Chrome bypass patterns.

    Chrome's `--proxy-bypass-list` does not consistently accept CIDR ranges, so the
    NoeticBraid/HelixMind fake-IP range is rendered as a wildcard.
    """

    if not fake_ip_range:
        return None
    value = fake_ip_range.strip()
    if value == "198.18.0.0/15":
        return "198.18.*.*"
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        raise ValueError(f"unsupported TUN CIDR (not parseable): {value}") from None
    if network.version == 4 and network.prefixlen in {8, 16, 24}:
        octets = str(network.network_address).split(".")
        wildcard_count = (32 - network.prefixlen) // 8
        return ".".join(octets[: 4 - wildcard_count] + ["*"] * wildcard_count)
    raise ValueError(f"unsupported TUN CIDR (Chrome rejects non-octet prefix): {value}")


def build_proxy_args(proxy_url: str | None, *, env: dict[str, str] | None = None) -> list[str]:
    """Build Chrome proxy arguments from explicit proxy and TUN environment."""

    if not proxy_url:
        return []
    source_env = env if env is not None else os.environ
    args = [f"--proxy-server={proxy_url}"]
    bypass = fake_ip_range_to_chrome_bypass(source_env.get("HELIXMIND_TRUST_FAKE_IP_RANGE"))
    if bypass:
        args.append(f"--proxy-bypass-list=<local>;{bypass}")
    return args


__all__ = ["build_proxy_args", "fake_ip_range_to_chrome_bypass"]
