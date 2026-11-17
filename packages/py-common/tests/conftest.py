"""Hypothesis settings.

In CI containers the filesystem is read-only, so the example database is disabled there
(set by AZINCO_ENV=ci) instead of producing warnings.
"""

from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile("ci", database=None, deadline=None)
settings.register_profile("dev", deadline=None)
settings.load_profile("ci" if os.environ.get("AZINCO_ENV") == "ci" else "dev")
