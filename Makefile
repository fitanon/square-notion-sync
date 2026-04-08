# FitAnon Square Sync v4 — Makefile
# Quick commands for managing the multi-account Square sync

.PHONY: help install status customers transactions export server sync test clean portal

help:
	@echo ""
	@echo "  FitAnon Square Sync v4"
	@echo "  ======================"
	@echo ""
	@echo "  Data:"
	@echo "    make status        Check account connections"
	@echo "    make customers     List customers (verbose)"
	@echo "    make transactions  List recent transactions (verbose)"
	@echo "    make export        Export data to JSON files"
	@echo ""
	@echo "  Sync:"
	@echo "    make sync          Trigger full Notion sync"
	@echo "    make sync-fin      Sync financial data only"
	@echo "    make sync-appts    Sync appointments only"
	@echo "    make sync-sessions Sync sessions only"
	@echo ""
	@echo "  Servers:"
	@echo "    make server        Start API server (port 8000)"
	@echo "    make portal        Start portal server (port 3000)"
	@echo ""
	@echo "  Dev:"
	@echo "    make install       Install all dependencies"
	@echo "    make test          Run test suite"
	@echo "    make clean         Remove generated files"
	@echo ""

# ── Setup ──────────────────────────────────────────

install:
	python3 -m venv venv
	. venv/bin/activate && pip install -r requirements.txt
	cd portal && npm install
	@echo ""
	@echo "✓ Python + Node dependencies installed"
	@echo "  1. source venv/bin/activate"
	@echo "  2. cp .env.example .env  (then fill in tokens)"
	@echo "  3. make status"

# ── Data Commands ──────────────────────────────────

status:
	@. venv/bin/activate && python cli.py status

customers:
	@. venv/bin/activate && python cli.py customers -v

transactions:
	@. venv/bin/activate && python cli.py transactions -v

export:
	@. venv/bin/activate && python cli.py export

# ── Sync Commands ──────────────────────────────────

sync:
	@. venv/bin/activate && python cli.py sync all

sync-fin:
	@. venv/bin/activate && python cli.py sync financial

sync-appts:
	@. venv/bin/activate && python cli.py sync appointments

sync-sessions:
	@. venv/bin/activate && python cli.py sync sessions

# ── Servers ────────────────────────────────────────

server:
	@. venv/bin/activate && python cli.py server

portal:
	cd portal && node server.js

# ── Development ────────────────────────────────────

test:
	@. venv/bin/activate && python -m pytest tests/ -v

clean:
	rm -rf exports/*.json
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
	@echo "✓ Cleaned"
