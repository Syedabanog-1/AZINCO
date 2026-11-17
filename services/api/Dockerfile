# syntax=docker/dockerfile:1
# AZINCO API image. Build context = repository root (needs packages/py-common).
#   runtime - production-like image (non-root, read-only friendly); also runs migrations
#   dev     - runtime + test/lint tools + tests (used by the `api-test` compose service)

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN groupadd --system --gid 10001 azinco \
 && useradd --system --uid 10001 --gid azinco --no-create-home --shell /usr/sbin/nologin azinco
COPY packages/py-common /src/py-common
COPY services/api/pyproject.toml services/api/README.md services/api/alembic.ini ./
COPY services/api/azinco_api ./azinco_api

FROM base AS runtime
RUN pip install /src/py-common .
USER azinco
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]
# 0.0.0.0 is required inside the container; the host only publishes it on 127.0.0.1.
CMD ["uvicorn", "azinco_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]

FROM base AS dev
RUN pip install "/src/py-common[dev]" ".[dev]"
COPY services/api/tests ./tests
COPY packages/py-common/tests ./common_tests
USER azinco
ENV MYPY_CACHE_DIR=/tmp/.mypy_cache
CMD ["pytest", "-p", "no:cacheprovider", "tests", "common_tests"]
