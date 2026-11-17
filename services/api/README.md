# azinco-api

AZINCO public REST API (FastAPI). See `docs/blueprint/02-architecture.md` §2.5.

```bash
pip install -e ".[dev]"
pytest
mypy
uvicorn azinco_api.main:create_app --factory --port 8000
```
