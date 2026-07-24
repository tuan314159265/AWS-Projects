#!/usr/bin/env bash
set -euo pipefail

S3_BUCKET="${1:?Usage: $0 <s3-bucket> <cloudfront-dist-id>}"
CLOUDFRONT_ID="${2:?Usage: $0 <s3-bucket> <cloudfront-dist-id>}"
PROFILE="${AWS_PROFILE:-default}"

echo "=== Building Next.js ==="
cd frontend
npm ci
npm run build

echo "=== Syncing to S3 ==="
aws s3 sync out/ "s3://$S3_BUCKET/" --delete --profile "$PROFILE"

echo "=== Invalidating CloudFront ==="
aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_ID" --paths "/*" --profile "$PROFILE"

echo "=== Done ==="