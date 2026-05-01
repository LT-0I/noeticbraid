# SPDX-License-Identifier: Apache-2.0
"""NoeticBraid backend service skeleton."""

from __future__ import annotations

from noeticbraid_backend.app import create_app
from noeticbraid_backend.settings import Settings

__version__ = "0.1.0a1"

__all__ = ["Settings", "create_app", "__version__"]
