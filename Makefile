.PHONY: help setup install test test-watch lint lint-fix type-check verify-setup

PYTHON ?= python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: $(VENV)/bin/activate install ## Create virtual environment and install dependencies
	@echo "Setup complete. Activate with: source $(VENV)/bin/activate"

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/activate ## Install development dependencies
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

test: ## Run tests with coverage (80% threshold)
	$(PYTEST) tests/ -v --cov=custom_components/meshtastic --cov-report=term-missing --cov-fail-under=80

test-watch: ## Run tests in watch mode
	$(PYTEST) tests/ -v --cov=custom_components/meshtastic -f

lint: ## Run linter and format checks
	$(RUFF) check .
	$(RUFF) format --check .

lint-fix: ## Run linter and formatter with auto-fix
	$(RUFF) check --fix .
	$(RUFF) format .

type-check: ## Run mypy type checking
	$(MYPY) custom_components/meshtastic --ignore-missing-imports

verify-setup: ## Verify all development prerequisites are installed
	@echo "=== Development Environment Verification ==="
	@echo ""
	@echo "Checking Python version..."
	@$(PYTHON) --version
	@$(PYTHON) -c "import sys; assert sys.version_info >= (3, 12), f'Python 3.12+ required, found {sys.version}'; print('✓ Python version OK')" 2>/dev/null || echo "✗ Python 3.12+ is required"
	@echo ""
	@echo "Checking virtual environment..."
	@test -d $(VENV) && echo "✓ Virtual environment exists" || echo "✗ Run 'make setup' first"
	@echo ""
	@echo "Checking tools..."
	@$(RUFF) --version 2>/dev/null && echo "✓ ruff" || echo "✗ ruff not found — run 'make install'"
	@$(MYPY) --version 2>/dev/null && echo "✓ mypy" || echo "✗ mypy not found — run 'make install'"
	@$(PYTEST) --version 2>/dev/null && echo "✓ pytest" || echo "✗ pytest not found — run 'make install'"
	@echo ""
	@echo "Checking dependencies..."
	@$(PIP) check 2>/dev/null && echo "✓ All dependencies satisfied" || echo "✗ Dependency issues found — run 'make install'"
	@echo ""
	@echo "Checking environment file..."
	@test -f .env && echo "✓ .env file exists" || echo "⚠ No .env file — copy from .env.example"
	@echo ""
	@echo "=== Verification Complete ==="
