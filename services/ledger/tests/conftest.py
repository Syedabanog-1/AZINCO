"""Hypothesis profile: no example database in read-only CI containers."""

from __future__ import annotations

import os

from hypothesis import settings

settings.register_profile("ci", database=None, deadline=None)
settings.register_profile("dev", deadline=None)
settings.load_profile("ci" if os.environ.get("AZINCO_ENV") == "ci" else "dev")
