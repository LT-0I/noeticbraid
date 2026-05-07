"""Outbound notification abstraction for SP-E."""

from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .errors import NotificationError
from .redaction import redact_text, redact_value

ALLOWED_OUTBOUND_LEVELS = ("silent_record", "low_priority", "normal", "requires_confirmation", "urgent_interrupt")
DEFAULT_URGENT_CHANNELS = ("lark", "dingtalk")


@dataclass(frozen=True)
class OutboundChannelConfig:
    channel: str
    enabled: bool = False
    webhook_url_env: str | None = None


@dataclass(frozen=True)
class OutboundDeliveryResult:
    level: str
    channel: str
    delivery: str
    reason: str
    event_written: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OutboundNotifier:
    def __init__(
        self,
        *,
        event_log_path: Path,
        channels: Mapping[str, OutboundChannelConfig] | None = None,
        urlopen: Callable[..., Any] | None = None,
        timeout_seconds: int = 10,
    ) -> None:
        self.event_log_path = Path(event_log_path)
        self.channels = dict(channels or {})
        self._urlopen = urlopen or urllib.request.urlopen
        self.timeout_seconds = int(timeout_seconds)

    def send(
        self,
        message: str,
        *,
        level: str,
        channel: str | Sequence[str] | None = "local",
        refs: Mapping[str, Any] | None = None,
    ) -> OutboundDeliveryResult | dict[str, Any]:
        if level not in ALLOWED_OUTBOUND_LEVELS:
            raise NotificationError(f"unknown level: {level}")
        refs = redact_value(dict(refs or {}))
        safe_message = redact_text(message, limit=2048)
        if level == "silent_record":
            return self._record_local_only(safe_message, level, refs)
        channels = self._resolve_channels(level, channel)
        if level == "urgent_interrupt":
            results = [self._dispatch_one(ch, safe_message, level, refs) for ch in channels]
            if not results:
                results = [self._dispatch_one("local", safe_message, level, refs)]
            return {"level": level, "channels": [item.to_dict() for item in results], "fanout": True, "event_written": True}
        return self._dispatch_with_fallback(channels, safe_message, level, refs)

    def _record_local_only(self, message: str, level: str, refs: Mapping[str, Any]) -> OutboundDeliveryResult:
        return self._record(
            level=level,
            channel="local",
            delivery="local_record",
            reason="silent_record",
            message=message,
            refs=refs,
        )

    def _resolve_channels(self, level: str, channel: str | Sequence[str] | None) -> list[str]:
        if isinstance(channel, str):
            return [channel]
        if channel is not None:
            return [str(item) for item in channel]
        if level == "urgent_interrupt":
            enabled = [name for name in DEFAULT_URGENT_CHANNELS if self.channels.get(name, OutboundChannelConfig(name)).enabled]
            return enabled or ["local"]
        return ["local"]

    def _dispatch_with_fallback(
        self,
        channels: Sequence[str],
        message: str,
        level: str,
        refs: Mapping[str, Any],
    ) -> OutboundDeliveryResult:
        attempted: list[OutboundDeliveryResult] = []
        for ch in channels or ["local"]:
            result = self._dispatch_one(ch, message, level, refs)
            attempted.append(result)
            if result.delivery == "sent" or result.channel == "local":
                return result
        return attempted[-1] if attempted else self._dispatch_one("local", message, level, refs)

    def _dispatch_one(self, channel: str | None, message: str, level: str, refs: Mapping[str, Any]) -> OutboundDeliveryResult:
        channel = channel or "local"
        reason = "local"
        delivery = "local_record"
        if channel == "telegram":
            reason = "telegram_disabled"
        elif channel != "local":
            config = self.channels.get(channel)
            if config is None:
                reason = "channel_not_configured"
            elif not config.enabled:
                reason = "channel_disabled"
            elif not config.webhook_url_env:
                reason = "missing_webhook_env_name"
            else:
                webhook_url = os.environ.get(config.webhook_url_env)
                if not webhook_url:
                    reason = "missing_webhook_env"
                else:
                    try:
                        self._send_webhook(webhook_url, channel=channel, level=level, message=message, refs=refs)
                    except Exception:
                        reason = "send_failed"
                    else:
                        delivery = "sent"
                        reason = "sent"
        return self._record(level=level, channel=channel, delivery=delivery, reason=reason, message=message, refs=refs)

    def _send_webhook(self, webhook_url: str, *, channel: str, level: str, message: str, refs: Mapping[str, Any]) -> None:
        if channel == "lark":
            payload = {"msg_type": "text", "content": {"text": f"[{level}] {message}"}}
        elif channel == "dingtalk":
            payload = {"msgtype": "text", "text": {"content": f"[{level}] {message}"}}
        else:
            payload = {"level": level, "message": message, "refs": redact_value(dict(refs))}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "noeticbraid-sp-e-scheduler/0.2"},
            method="POST",
        )
        with self._urlopen(request, timeout=self.timeout_seconds) as response:
            response.read()

    def _record(
        self,
        *,
        level: str,
        channel: str,
        delivery: str,
        reason: str,
        message: str,
        refs: Mapping[str, Any],
    ) -> OutboundDeliveryResult:
        self.event_log_path.parent.mkdir(parents=True, exist_ok=True)
        event = redact_value(
            {
                "ts": dt.datetime.now(tz=dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
                "event_type": "outbound_notify",
                "level": level,
                "channel": channel,
                "delivery": delivery,
                "reason": reason,
                "message": message,
                "refs": dict(refs),
            }
        )
        with self.event_log_path.open("a", encoding="utf-8") as handle:
            json.dump(event, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return OutboundDeliveryResult(level=level, channel=channel, delivery=delivery, reason=reason, event_written=True)
