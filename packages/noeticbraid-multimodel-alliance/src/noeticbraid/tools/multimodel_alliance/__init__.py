"""SP-B Multimodel Alliance Runtime public API."""

from .convergence import ConvergenceError, converge
from .debate_runner import DebateError, run_debate
from .loop import DebateLoopError, run_debate_loop
from .provider_round_parser import ProviderRoundParseError, build_real_rounds, parse_provider_artifact
from .router import RoutingError, route
from .validator import (
    ValidationError,
    validate_all,
    validate_convergence_record,
    validate_debate_record,
    validate_fixture,
    validate_route_record,
)

__all__ = [
    "ConvergenceError",
    "DebateError",
    "DebateLoopError",
    "ProviderRoundParseError",
    "RoutingError",
    "ValidationError",
    "converge",
    "route",
    "run_debate_loop",
    "run_debate",
    "build_real_rounds",
    "parse_provider_artifact",
    "validate_all",
    "validate_convergence_record",
    "validate_debate_record",
    "validate_fixture",
    "validate_route_record",
]
