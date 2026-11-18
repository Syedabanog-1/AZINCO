# ADR-0013: Hosting and region

| Field | Value |
|---|---|
| Status | Open — owner decision DEC-10 |
| Date | 2026-11-18 |
| Base Standard | §12 (privacy laws per jurisdiction, backups), §11.2 (Docker, CI/CD) |
| Gaps | GAP-OPS-02 (regions / data residency), GAP-LEG-03 (privacy obligations) |

## Criteria for the decision
Data-residency needs of PK, UK, US, CA, AU clients; managed PostgreSQL with point-in-time recovery;
KMS availability (ADR-0007); object storage with server-side encryption; container hosting;
cost; latency from Pakistan and the first international market (DEC-01).

## Options to compare
| Option | Notes |
|---|---|
| One major cloud, one region first, more regions per residency demand | Simplest operations; residency handled by adding regions |
| Separate deployments per jurisdiction group | Strong residency; higher cost and ops |
| Local data-centre provider for PK + cloud for others | Possible residency fit; two operating models |

Until decided, everything runs locally in Docker with synthetic data only.
