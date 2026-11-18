# ADR-0014: Local object storage image — Chainguard MinIO build, swappable

| Field | Value |
|---|---|
| Status | Accepted (Step 0.2) |
| Date | 2026-11-18 |
| Base Standard | §11.2 (encrypted S3-compatible storage; MinIO locally) |

## Context
MinIO stopped publishing community container images in October 2025, so the usual `minio/minio`
tags are no longer a dependable local default.

## Decision
Local development uses a maintained Chainguard MinIO image, selectable with `S3_IMAGE`; buckets are
created by the one-shot `storage-init` service (AWS CLI). Code talks only to the S3 API, so the
image (or a cloud bucket in staging) can be swapped without code changes.

## Consequences
`verify_stack` checks that the buckets exist. Production storage is decided with hosting (ADR-0013).
