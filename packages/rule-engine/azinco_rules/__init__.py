"""AZINCO rule engine: versioned jurisdiction rule packs and a pure decision-table evaluator.

No rates, thresholds or deadlines live here - only in governed, cited packs (BS §6.6, §8.2).
"""

from azinco_rules.engine import (
    AmbiguousRuleError,
    FactError,
    NoPackError,
    PackLoadError,
    Registry,
    Result,
    RuleEngineError,
    activation_problems,
    content_hash,
    evaluate,
    load_pack,
    run_pack_tests,
)
from azinco_rules.model import Layer, RulePack, Status

__version__ = "0.1.0"

__all__ = [
    "AmbiguousRuleError",
    "FactError",
    "Layer",
    "NoPackError",
    "PackLoadError",
    "Registry",
    "Result",
    "RuleEngineError",
    "RulePack",
    "Status",
    "activation_problems",
    "content_hash",
    "evaluate",
    "load_pack",
    "run_pack_tests",
]
