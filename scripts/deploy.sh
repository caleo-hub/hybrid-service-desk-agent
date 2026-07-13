#!/usr/bin/env bash
set -euo pipefail
source .env 2>/dev/null || true
export AWS_PROFILE="${AWS_PROFILE:-dev}" AWS_REGION="${AWS_REGION:-us-east-1}"
export PATH="/home/caleo/.local/bin:$PATH"
cd infrastructure/cdk && npm ci && npx cdk deploy --all --require-approval never
cd ../..
./scripts/export-outputs.sh
