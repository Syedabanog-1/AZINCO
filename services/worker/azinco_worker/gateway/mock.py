"""[MOCK] provider: deterministic, offline, free. The default in Phase 0 and in every test.

It answers from registered fixtures (task -> callable) so graphs can be exercised end to end
without a real model. It never invents amounts: fixtures return labels and scores only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from azinco_worker.gateway.core import ProviderReply, RenderedPrompt, Usage

Fixture = Callable[[RenderedPrompt], Mapping[str, object] | str]


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)  # rough, deterministic estimate for budget tests


@dataclass
class MockProvider:
    name: str = "mock"
    fixtures: dict[str, Fixture] = field(default_factory=dict)
    calls: list[tuple[str, RenderedPrompt]] = field(default_factory=list)

    def register(self, task: str, fixture: Fixture) -> None:
        self.fixtures[task] = fixture

    def complete(
        self,
        prompt: RenderedPrompt,
        *,
        model: str,
        schema: Mapping[str, object],
        task: str,
        max_output_tokens: int,
    ) -> ProviderReply:
        self.calls.append((task, prompt))
        fixture = self.fixtures.get(task)
        if fixture is None:
            raise LookupError(f"[MOCK] no fixture registered for task {task!r}")
        answer = fixture(prompt)
        text = answer if isinstance(answer, str) else json.dumps(answer, sort_keys=True)
        return ProviderReply(
            text=text,
            usage=Usage(
                input_tokens=_tokens(prompt.system + prompt.user),
                output_tokens=min(_tokens(text), max_output_tokens),
            ),
            model=f"mock-{model}",
        )


def stable_score(text: str) -> float:
    """Deterministic pseudo-confidence in [0.50, 0.99] for [MOCK] fixtures."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return round(0.5 + (digest[0] / 255) * 0.49, 2)
