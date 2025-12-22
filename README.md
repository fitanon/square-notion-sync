# Square Callouts Starter (Perplexity + Comet integration)

Minimal starter to demonstrate how to call Square APIs (payments/orders) from Python, enrich or verify results via Perplexity AI, and log experiments/metrics with Comet ML.

Important: Do NOT commit your secrets. Use environment variables or a secrets manager.

Quick start (macOS / zsh)

1. Copy `.env.example` to `.env` and fill in credentials (do not commit `.env`).

```bash
cd square-callouts-starter
cp .env.example .env
# edit .env and add your tokens
```

2. Create a virtual environment and install dependencies (script included):

```bash
./install-perplexity.sh
```

3. Run the example callout (this will call Square's sandbox or production depending on env):

```bash
python3 -m src.callouts
```

Files
- `install-perplexity.sh` — creates venv and installs requirements
- `requirements.txt` — Python packages used
- `.env.example` — example environment variables (no secrets)
- `src/callouts.py` — example code showing Square API call, Perplexity query, and Comet logging

Square notes
- For local testing prefer Square Sandbox endpoints. Set `SQUARE_ENV=sandbox` in `.env` and populate `SQUARE_SANDBOX_ACCESS_TOKEN`.
- For production use the live endpoints and `SQUARE_ACCESS_TOKEN`.

Security
- Never check secrets into git. Use `.env` only for local development and a real secrets manager (Vercel/Netlify environment variables or HashiCorp Vault) in production.
