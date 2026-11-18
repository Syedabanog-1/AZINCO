"""Predictors that turn the platform's real code paths into golden-set runs."""

from __future__ import annotations

from azinco_worker.gateway import ModelGateway
from azinco_worker.goldens.core import Prediction, Predictor, PredictorInfo
from azinco_worker.goldens.model import Item
from azinco_worker.graph.review import (
    CATEGORIZE_PROMPT_VERSION,
    CategoryProposal,
    categorize_request,
)


def gateway_categorizer(gateway: ModelGateway) -> tuple[Predictor, PredictorInfo]:
    """Categorisation through the Model Gateway - exactly what the review graph's `prepare` does."""
    route = gateway.route_for("categorization")

    def predict(item: Item) -> Prediction:
        result = gateway.complete(categorize_request(item.document), CategoryProposal)
        return Prediction(account_code=result.output.account_code)

    info = PredictorInfo(
        predictor_id="gateway:categorization",
        provider=route.provider,
        model=route.model,
        prompt_version=CATEGORIZE_PROMPT_VERSION,
    )
    return predict, info
