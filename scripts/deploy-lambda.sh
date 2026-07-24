#!/usr/bin/env bash
set -euo pipefail

LAMBDA_NAME="${1:?Usage: $0 <lambda-name> <zip-path>}"
ZIP_PATH="${2:?Usage: $0 <lambda-name> <zip-path>}"
PROFILE="${AWS_PROFILE:-default}"

echo "=== Deploying $LAMBDA_NAME ==="
aws lambda update-function-code \
  --function-name "$LAMBDA_NAME" \
  --zip-file "fileb://$ZIP_PATH" \
  --profile "$PROFILE" \
  --no-cli-pager

echo "=== Done ==="