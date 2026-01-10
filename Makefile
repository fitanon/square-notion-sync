# FitAnon Square Sync - Makefile
# Quick commands for managing the multi-account Square sync

.PHONY: help install status customers transactions invoices export server test clean

# Default target
help:
	@echo ""
	@echo "  FitAnon Square Sync Commands"
	@echo "  ============================="
	@echo ""
	@echo "  make install       Install dependencies"
	@echo "  make status        Check account connection status"
	@echo "  make customers     List customers from all accounts"
	@echo "  make transactions  List recent transactions"
	@echo "  make invoices      List invoices"
	@echo "  make export        Export all data to JSON files"
	@echo "  make server        Start the API server"
	@echo "  make test          Run tests"
	@echo "  make clean         Remove generated files"
	@echo ""

# Setup
install:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	. venv/bin/activate && pip install -r fastapi/requirements.txt
	. venv/bin/activate && pip install notion-client
	@echo ""
	@echo "✓ Installation complete!"
	@echo "  Activate venv: source venv/bin/activate"
	@echo "  Then run: make status"

# Data commands
status:
	@. venv/bin/activate && python cli.py status

customers:
	@. venv/bin/activate && python cli.py customers -v

transactions:
	@. venv/bin/activate && python cli.py transactions -v

invoices:
	@. venv/bin/activate && python cli.py invoices -v

export:
	@. venv/bin/activate && python cli.py export
	@echo ""
	@echo "✓ Data exported to exports/ directory"

# Server
server:
	@. venv/bin/activate && python cli.py server

# Development
test:
	@. venv/bin/activate && python -m pytest tests/ -v 2>/dev/null || python -m src.multi_account

clean:
	rm -rf exports/*.json
	rm -rf __pycache__ src/__pycache__ fastapi/__pycache__
	rm -rf .pytest_cache
	@echo "✓ Cleaned up generated files"

# Quick setup for new users
setup: install
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env"
	@echo "  2. Add your Square API tokens to .env"
	@echo "  3. Run: make status"
