"""[MOCK] wiring used by tests and local demos: a gateway whose only provider is the mock."""

from __future__ import annotations

from collections.abc import Mapping

from azinco_worker.gateway import (
    Budget,
    MockProvider,
    ModelGateway,
    RenderedPrompt,
    Route,
    stable_score,
)
from azinco_worker.graph.review import CATEGORIZE_TASK


def _categorize(prompt: RenderedPrompt) -> Mapping[str, object]:
    return {
        "account_code": "6000",
        "label": "[MOCK] Rent expense",
        "confidence": stable_score(prompt.user),
        "reasons": ["[MOCK] fixture answer - not a real model"],
    }


def mock_gateway(budget: Budget | None = None) -> tuple[ModelGateway, MockProvider]:
    provider = MockProvider()
    provider.register(CATEGORIZE_TASK, _categorize)
    gateway = ModelGateway(
        providers={"mock": provider},
        routes={"default": Route(provider="mock", model="fixture")},
        budget=budget or Budget(),
    )
    return gateway, provider
