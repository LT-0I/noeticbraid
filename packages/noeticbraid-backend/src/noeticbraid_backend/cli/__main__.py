# SPDX-License-Identifier: Apache-2.0
"""Console-script dispatcher for NoeticBraid backend utilities."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence

from noeticbraid_backend.omc_workspace import cli_adopt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="noeticbraid", description="NoeticBraid command-line utilities")
    subparsers = parser.add_subparsers(dest="command")

    omc_parser = subparsers.add_parser("omc", help="OMC ingestion workspace commands")
    omc_subparsers = omc_parser.add_subparsers(dest="omc_command")

    adopt_parser = omc_subparsers.add_parser("adopt-candidate", help="Explicitly adopt an OMC candidate")
    cli_adopt.add_arguments(adopt_parser)
    adopt_parser.set_defaults(handler=cli_adopt._run)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    handler: Callable[[argparse.Namespace], int] | None = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(sys.stderr)
        return 2
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
