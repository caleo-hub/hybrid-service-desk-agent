SHELL := /bin/bash
PYTHON ?= python3
.PHONY: install doctor dev verify deploy seed destroy synth
install:
	@$(PYTHON) --version
doctor:
	@AWS_PROFILE=$${AWS_PROFILE:-dev} AWS_REGION=$${AWS_REGION:-us-east-1} aws sts get-caller-identity >/dev/null
	@echo "Pronto: perfil AWS disponível."
dev:
	@PORT=3100 $(PYTHON) services/api/app.py
verify:
	@$(PYTHON) -m unittest discover -s tests -v
synth:
	@cd infrastructure/cdk && npm ci && npm run synth
deploy:
	@./scripts/deploy.sh
seed:
	@./scripts/seed.sh
destroy:
	@./scripts/destroy.sh
