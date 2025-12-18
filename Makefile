COMPOSE ?= docker compose
ENV_FILE ?= .env

.PHONY: install lint test cov clean up down ps logs restart healthcheck

# Local development
install:
	pip install -e .

lint:
	ruff check .

test:
	PYTHONPATH=. pytest

cov:
	PYTHONPATH=. pytest --cov=app --cov-report=term-missing --cov-report=html:htmlcov

clean:
	rm -rf htmlcov .coverage .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker commands
up:
	$(COMPOSE) --env-file $(ENV_FILE) up -d

down:
	$(COMPOSE) --env-file $(ENV_FILE) down

ps:
	$(COMPOSE) --env-file $(ENV_FILE) ps

logs:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f

logs-%:
	$(COMPOSE) --env-file $(ENV_FILE) logs -f $*

restart:
	$(COMPOSE) --env-file $(ENV_FILE) down && $(COMPOSE) --env-file $(ENV_FILE) up -d

healthcheck:
	@echo "Checking services..."
	@curl -fsS http://localhost:9000/minio/health/live >/dev/null && echo "minio: OK" || echo "minio: FAIL"
	@$(COMPOSE) --env-file $(ENV_FILE) exec -T postgres pg_isready -U postgres -d charmelio -h 127.0.0.1 >/dev/null && echo "postgres: OK" || echo "postgres: FAIL"
	@curl -fsS http://localhost:8233/ >/dev/null && echo "temporal-ui: OK" || echo "temporal-ui: FAIL"
	@curl -fsS http://localhost:8000/health >/dev/null && echo "api: OK" || echo "api: FAIL"
	@echo "Done."
