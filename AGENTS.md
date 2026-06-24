# AGENTS.md

## Cursor Cloud specific instructions

This repo is a Python service (no Node, no Docker, no local database). Standard
commands live in `README.md`, `CLAUDE.md`, and the `Makefile` (e.g. `make
install`, `make status`, `make test`, `make customers`). The notes below only
cover non-obvious caveats discovered while setting up the environment.

### Services / surfaces
- **CLI** (`python cli.py {status,customers,transactions,invoices,export,server}`) — queries Square accounts and prints/exports JSON. The documented `make`/`cli.py` commands work as-is.
- **FastAPI REST API** (port 8000) — the `fastapi/` app (`/health`, `/accounts`, `/customers`, `/transactions`, `/invoices`, `/summary`, `/sync/customer/{id}`, OAuth router, Swagger at `/docs`). See the "Running the API server" caveat below — the documented launch command does **not** work.
- All Square calls hit the live Square API; there is no local datastore. State is just `fastapi/tokens.json` and `exports/*.json`.

### Environment / credentials
- Copy `.env.example` → `.env`. With no Square token the app still runs but reports **0 connected accounts** (graceful degradation), and `/customers` etc. return empty lists. To exercise real data you must supply a Square token via `ACCOUNT__{NAME}__TOKEN` (names: `FITCLINIC_LLC`, `FITCLINIC`, `FITNESSWITHMIKE`) or `SQUARE_ACCESS_TOKEN`, plus `SQUARE_ENV=sandbox|production`.
- Optional integrations are skipped silently unless their env vars are set: Notion (`NOTION_TOKEN` + `NOTION_DATABASE_ID`), Square OAuth (`SQUARE_APPLICATION_ID`/`_SECRET`/`_OAUTH_REDIRECT_URI`), Google Sheets, Perplexity, Comet ML.

### Running the API server (IMPORTANT non-obvious caveat)
The local app directory is named `fastapi/` and has **no `__init__.py`**, so it is a
namespace package that gets shadowed by the installed `fastapi` framework package.
As a result, **both documented commands fail**:
`uvicorn fastapi.app:app` (README/CLAUDE.md/`make server`) → "Could not import module fastapi.app", and
`cd fastapi && uvicorn app:app` (fastapi/README.md) → "attempted relative import with no known parent package".

Run the server by loading the app under a non-colliding package name (no source
changes needed):

```bash
source venv/bin/activate
python - <<'PY'
import importlib.util, sys, types, uvicorn
sys.path.insert(0, '.')
pkg = types.ModuleType('localapi'); pkg.__path__ = ['fastapi']; sys.modules['localapi'] = pkg
for s in ['accounts', 'notion_helper', 'token_store', 'oauth', 'app']:
    sp = importlib.util.spec_from_file_location('localapi.' + s, 'fastapi/' + s + '.py')
    m = importlib.util.module_from_spec(sp); sys.modules['localapi.' + s] = m; sp.loader.exec_module(m)
uvicorn.run(sys.modules['localapi.app'].app, host='0.0.0.0', port=8000)
PY
```

(`--reload` requires an import string, which this collision prevents; restart the process to pick up code changes.)

### Tests & lint
- `make test` runs `pytest tests/ || python -m src.multi_account`. There is **no `tests/` directory**, so it always falls back to executing the module (prints an account summary; not a real test suite).
- No linter is configured (no ruff/flake8/black/pylint config). Use `python -m py_compile` for a quick syntax check.

### System dependency
- `python3-venv` (Debian/Ubuntu) is required for `make install`; it is installed in the VM snapshot, so it is intentionally not in the update script.
