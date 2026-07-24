#!/usr/bin/env bash
set -euo pipefail

OUTDIR="build/lambdas"
mkdir -p "$OUTDIR"

build_lambda() {
  local name="$1" dir="$2"
  echo "=== Building $name ==="
  cd "$dir"
  rm -rf build_lambda
  mkdir build_lambda
  cp -r *.py requirements.txt build_lambda/
  pip install -r requirements.txt -t build_lambda/ --quiet
  cd build_lambda
  zip -r "../../$OUTDIR/${name}.zip" . > /dev/null
  cd ../..
  echo "  -> $OUTDIR/${name}.zip"
}

build_lambda "consumer" "consumer"
build_lambda "etl" "etl"
build_lambda "rag-api" "search"

echo "=== All lambdas built in $OUTDIR/ ==="