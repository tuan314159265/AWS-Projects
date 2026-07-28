#!/usr/bin/env bash
set -euo pipefail

S3_BUCKET="${1:?Usage: $0 <s3-bucket> <cloudfront-dist-id> [api-url]}"
CLOUDFRONT_ID="${2:?Usage: $0 <s3-bucket> <cloudfront-dist-id> [api-url]}"
API_URL="${3:-${VITE_API_URL:-}}"
PROFILE="${AWS_PROFILE:-default}"

if [[ -z "$API_URL" ]]; then
  echo "VITE_API_URL is required when deploying the frontend to S3." >&2
  exit 1
fi

echo "=== Building Vite frontend ==="
cd frontend
VITE_API_URL="$API_URL" npm install
VITE_API_URL="$API_URL" npm run build

echo "=== Syncing to S3 ==="
aws s3 sync dist/ "s3://$S3_BUCKET/" --delete --profile "$PROFILE"

echo "=== Invalidating CloudFront ==="
aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_ID" --paths "/*" --profile "$PROFILE"

echo "=== Done ==="
