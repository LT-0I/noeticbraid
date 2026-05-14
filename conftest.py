# SPDX-License-Identifier: Apache-2.0
"""Pytest bootstrap for HOME-stripped local CI simulations.

Some developer machines install test-only web dependencies in the login user's
PEP-370 site directory.  The SDD-D4-01 CI-simulation intentionally strips HOME
to prove project code does not read user files, but Python also stops adding the
login user's site-packages in that mode.  Re-add only that package directory
when it exists so the exact HOME-stripped pytest command exercises the same
installed dependencies without depending on HOME.
"""

from __future__ import annotations

import os
import pwd
import sys
from pathlib import Path


def _restore_login_user_site_packages() -> None:
    try:
        login_home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    except (KeyError, OSError):
        return
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    site_packages = login_home / ".local" / "lib" / version / "site-packages"
    site_packages_text = str(site_packages)
    if site_packages.is_dir() and site_packages_text not in sys.path:
        sys.path.insert(0, site_packages_text)


_restore_login_user_site_packages()
