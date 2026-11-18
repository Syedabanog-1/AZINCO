# ADR-0010: OCR engine

| Field | Value |
|---|---|
| Status | Open — decision by spike at the start of Phase 1 (DEC-09) |
| Date | 2026-11-18 |
| Base Standard | §7.3 (Document Ingestion Agent: OCR + vision), §13 (extraction accuracy) |

## Plan
Run the same synthetic golden set (EN, plus Urdu where available; clean, noisy, adversarial) through
candidate engines and pick by field accuracy, cost per page, latency and data-residency fit:

| Candidate class | Examples | Notes |
|---|---|---|
| Open-source, self-hosted | Tesseract, PaddleOCR | No data leaves our hosting; quality varies on noisy scans |
| Cloud OCR | Major cloud document-AI services | Strong accuracy; needs DPA and region fit (GAP-LEG-03, ADR-0013) |
| Vision LLM via Model Gateway | Provider models through ADR-0004 | Flexible; must pass the same golden set and masking rules |

Decision recorded here with the golden-set report; ≥ 98% field accuracy on the clean synthetic set
is the Phase 1 target (BS §13).
