from __future__ import annotations

import pytest

from noeticbraid_runtime._proxy import build_proxy_args, fake_ip_range_to_chrome_bypass


def test_fake_ip_range_to_chrome_bypass_converts_helixmind_cidr() -> None:
    assert fake_ip_range_to_chrome_bypass("198.18.0.0/15") == "198.18.*.*"


def test_build_proxy_args_includes_proxy_and_tun_bypass(monkeypatch) -> None:
    monkeypatch.setenv("HELIXMIND_TRUST_FAKE_IP_RANGE", "198.18.0.0/15")

    args = build_proxy_args("socks5://127.0.0.1:7890")

    assert "--proxy-server=socks5://127.0.0.1:7890" in args
    assert "--proxy-bypass-list=<local>;198.18.*.*" in args


def test_build_proxy_args_empty_without_proxy(monkeypatch) -> None:
    monkeypatch.delenv("HELIXMIND_TRUST_FAKE_IP_RANGE", raising=False)

    assert build_proxy_args(None) == []


def test_fake_ip_range_rejects_non_octet_aligned_cidr() -> None:
    with pytest.raises(ValueError, match="unsupported TUN CIDR"):
        fake_ip_range_to_chrome_bypass("10.0.0.0/12")


def test_fake_ip_range_rejects_unparseable_cidr() -> None:
    with pytest.raises(ValueError, match="unsupported TUN CIDR"):
        fake_ip_range_to_chrome_bypass("not-a-cidr")
