# SPDX-License-Identifier: Apache-2.0
"""Platform artifact persistence and download routes."""

from noeticbraid_backend.platform.artifacts.store import Artifact, persist

__all__ = ["Artifact", "persist"]
