#!/usr/bin/env bash
set -euo pipefail
source .env 2>/dev/null || true
export AWS_PROFILE="${AWS_PROFILE:-dev}" AWS_REGION="${AWS_REGION:-us-east-1}"
read -r -p "Destruir as stacks temporárias do Service Desk em $AWS_REGION? [y/N] " ok
[[ "$ok" =~ ^[Yy]$ ]] && (cd infrastructure/cdk && npx cdk destroy --all) || true
