#!/usr/bin/env bash
set -euo pipefail
source .env 2>/dev/null || true
export AWS_PROFILE="${AWS_PROFILE:-dev}" AWS_REGION="${AWS_REGION:-us-east-1}"
export PATH="/home/caleo/.local/bin:$PATH"
stack=HybridServiceDeskDemo
value(){ aws cloudformation describe-stacks --stack-name "$stack" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text; }
api_url="$(value ApiUrl)"; catalog_table="$(value CatalogTable)"
cat > .env.aws <<EOF
CATALOG_TABLE=$catalog_table
AWS_REGION=$AWS_REGION
EOF
cat > apps/web/config.local.js <<EOF
window.APP_CONFIG = { apiUrl: '$api_url' };
EOF
echo "Outputs exportados. Frontend local apontará para $api_url"
