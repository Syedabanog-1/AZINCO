"""Model Gateway (ADR-0004). Agents call this, never a provider SDK."""

from azinco_worker.gateway.core import (
    Budget,
    BudgetExceededError,
    CallRecord,
    GatewayError,
    GatewayResult,
    ModelGateway,
    ModelRequest,
    OutputValidationError,
    Provider,
    ProviderNotConfiguredError,
    ProviderReply,
    RenderedPrompt,
    Route,
    Usage,
    mask,
    render,
)
from azinco_worker.gateway.mock import MockProvider, stable_score

__all__ = [
    "Budget",
    "BudgetExceededError",
    "CallRecord",
    "GatewayError",
    "GatewayResult",
    "MockProvider",
    "ModelGateway",
    "ModelRequest",
    "OutputValidationError",
    "Provider",
    "ProviderNotConfiguredError",
    "ProviderReply",
    "RenderedPrompt",
    "Route",
    "Usage",
    "mask",
    "render",
    "stable_score",
]
