"""CLI runner whitelist registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .errors import CliRunnerRegistryError


@dataclass(frozen=True)
class CliRunnerSpec:
    """Immutable CLI runner specification.

    Attributes:
        name: Logical runner name (e.g. "echo", "git").
        command: Argv prefix (e.g. ["echo"], ["git", "status"]).
        env: Environment variable overrides (default empty dict).
        timeout_sec: Hard timeout in seconds (must be > 0).
        stdin_allowed: Whether stdin can be piped (default False).
    """

    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    timeout_sec: int = 60
    stdin_allowed: bool = False


class CliRunnerRegistry:
    """In-memory whitelist of allowed CLI runners.

    Initial entry: "echo" (timeout 5s, no env, no stdin) — useful for tests.
    """

    def __init__(self) -> None:
        self._runners: dict[str, CliRunnerSpec] = {}
        self.register(
            CliRunnerSpec(
                name="echo",
                command=["echo"],
                env={},
                timeout_sec=5,
                stdin_allowed=False,
            )
        )

    def register(self, spec: CliRunnerSpec) -> None:
        if not spec.name:
            raise CliRunnerRegistryError("runner name must be non-empty")
        if spec.name in self._runners:
            raise CliRunnerRegistryError(f"runner already registered: {spec.name!r}")
        if spec.timeout_sec <= 0:
            raise CliRunnerRegistryError(
                f"runner {spec.name!r} timeout_sec must be > 0; got {spec.timeout_sec}"
            )
        if not spec.command:
            raise CliRunnerRegistryError(
                f"runner {spec.name!r} command must be non-empty list"
            )
        self._runners[spec.name] = spec

    def lookup(self, name: str) -> Optional[CliRunnerSpec]:
        return self._runners.get(name)

    def list_allowed(self) -> list[str]:
        return sorted(self._runners.keys())
