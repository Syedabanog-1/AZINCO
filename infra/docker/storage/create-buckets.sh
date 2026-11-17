#!/usr/bin/env bash
# AZINCO Step 0.2 — create S3 buckets on the local [MOCK] object storage.
# Uses only the standard S3 API (aws-cli), so it works with any S3-compatible server.
set -euo pipefail

: "${S3_INTERNAL_ENDPOINT:?}" "${S3_BUCKET_DOCUMENTS:?}" "${S3_BUCKET_ARCHIVE:?}"
s3() { aws --endpoint-url "$S3_INTERNAL_ENDPOINT" "$@"; }

echo "Waiting for object storage at $S3_INTERNAL_ENDPOINT ..."
for attempt in $(seq 1 60); do
  if s3 s3api list-buckets >/dev/null 2>&1; then
    echo "Object storage is ready (attempt $attempt)."
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo "ERROR: object storage not reachable after 60 attempts" >&2
    exit 1
  fi
  sleep 2
done

bucket_exists() { s3 s3api head-bucket --bucket "$1" >/dev/null 2>&1; }

# Documents bucket: versioned, private.
if bucket_exists "$S3_BUCKET_DOCUMENTS"; then
  echo "Bucket $S3_BUCKET_DOCUMENTS already exists."
else
  s3 s3api create-bucket --bucket "$S3_BUCKET_DOCUMENTS"
  echo "Created $S3_BUCKET_DOCUMENTS"
fi
s3 s3api put-bucket-versioning --bucket "$S3_BUCKET_DOCUMENTS" \
  --versioning-configuration Status=Enabled

# Archive bucket: object lock (immutability for archives & audit anchors, BS §6.8, §12).
if bucket_exists "$S3_BUCKET_ARCHIVE"; then
  echo "Bucket $S3_BUCKET_ARCHIVE already exists."
else
  s3 s3api create-bucket --bucket "$S3_BUCKET_ARCHIVE" --object-lock-enabled-for-bucket
  echo "Created $S3_BUCKET_ARCHIVE with object lock"
fi

# Block any public access policy (defence in depth; buckets are private by default).
for b in "$S3_BUCKET_DOCUMENTS" "$S3_BUCKET_ARCHIVE"; do
  s3 s3api put-public-access-block --bucket "$b" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
    >/dev/null 2>&1 || echo "Note: public-access-block not supported by this server (buckets remain private)."
done

s3 s3api list-buckets --query "Buckets[].Name" --output text
echo "storage-init: OK"
