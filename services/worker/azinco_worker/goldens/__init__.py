"""Golden-set framework (governance: docs/governance/golden-set-plan.md)."""

from azinco_worker.goldens.core import (
    GoldenSet,
    GoldenSetError,
    Prediction,
    PredictorInfo,
    Report,
    compare,
    load_set,
    run,
    score,
    write_set,
)
from azinco_worker.goldens.model import Item, Manifest, SetStatus

__all__ = [
    "GoldenSet",
    "GoldenSetError",
    "Item",
    "Manifest",
    "Prediction",
    "PredictorInfo",
    "Report",
    "SetStatus",
    "compare",
    "load_set",
    "run",
    "score",
    "write_set",
]
