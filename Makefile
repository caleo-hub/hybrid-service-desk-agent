SHELL := /bin/bash
PYTHON ?= python3
UV ?= $(shell command -v uv 2>/dev/null || echo /home/caleo/.local/bin/uv)
AWS ?= /home/caleo/.local/bin/aws
.PHONY: install doctor dev verify deploy seed destroy synth
install:
	@$(UV) venv --allow-existing .venv
	@$(UV) pip install --python .venv/bin/python -r requirements-dev.txt
doctor:
	@AWS_PROFILE=$${AWS_PROFILE:-dev} AWS_REGION=$${AWS_REGION:-us-east-1} $(AWS) sts get-caller-identity >/dev/null
	@echo "Pronto: perfil AWS disponível."
dev:
	@PORT=3100 $(PYTHON) services/api/app.py
verify:
	@$(MAKE) install
	@.venv/bin/python -m unittest discover -s tests -v
synth:
	@cd infrastructure/cdk && npm ci && npm run synth
deploy:
	@./scripts/deploy.sh
seed:
	@./scripts/seed.sh
destroy:
	@./scripts/destroy.sh
