# syntax=docker/dockerfile:1
# AZINCO worker image. Build context = repository root.
#   runtime - Model Gateway + LangGraph graphs (no queue consumer yet; Phase 1)
#   dev     - runtime + tests/lint (used by the `worker-test` compose service)

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10
WORKDIR /app
RUN groupadd --system --gid 10001 azinco \
 && useradd --system --uid 10001 --gid azinco --no-create-home --shell /usr/sbin/nologin azinco
COPY services/worker/pyproject.toml services/worker/README.md ./
COPY services/worker/azinco_worker ./azinco_worker

FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/pip pip install .
USER azinco
CMD ["python", "-c", "import azinco_worker; print('azinco-worker', azinco_worker.__version__, '- no queue consumer until Phase 1')"]

FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/pip pip install ".[dev]"
COPY services/worker/tests ./tests
USER azinco
ENV MYPY_CACHE_DIR=/tmp/.mypy_cache
CMD ["sh", "-c", "pytest -p no:cacheprovider tests && mypy && ruff check --no-cache . && echo WORKER-TESTS-OK"]
