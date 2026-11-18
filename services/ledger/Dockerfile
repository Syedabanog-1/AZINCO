# syntax=docker/dockerfile:1
# AZINCO Ledger Service image. Build context = repository root (needs packages/py-common).
#   runtime - internal-only service (non-root, read-only); never published to the host
#   dev     - runtime + tests/lint (used by the `ledger-test` compose service)

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10
WORKDIR /app
RUN groupadd --system --gid 10001 azinco \
 && useradd --system --uid 10001 --gid azinco --no-create-home --shell /usr/sbin/nologin azinco
COPY packages/py-common /src/py-common
COPY services/ledger/pyproject.toml services/ledger/README.md ./
COPY services/ledger/azinco_ledger ./azinco_ledger

FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/pip pip install /src/py-common .
USER azinco
EXPOSE 8100
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8100/health', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "azinco_ledger.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]

FROM base AS dev
RUN --mount=type=cache,target=/root/.cache/pip pip install /src/py-common ".[dev]"
COPY services/ledger/tests ./tests
USER azinco
ENV MYPY_CACHE_DIR=/tmp/.mypy_cache
CMD ["sh", "-c", "pytest -p no:cacheprovider tests && mypy && ruff check --no-cache . && echo LEDGER-TESTS-OK"]
