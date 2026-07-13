#!/usr/bin/env bash
set -euo pipefail
source .env 2>/dev/null || true
export AWS_PROFILE="${AWS_PROFILE:-dev}" AWS_REGION="${AWS_REGION:-us-east-1}"
export PATH="/home/caleo/.local/bin:$PATH"
[[ -f .env.aws ]] || ./scripts/export-outputs.sh
set -a; source .env.aws; set +a
[[ -x .venv/bin/python ]] || make install
.venv/bin/python scripts/seed.py
