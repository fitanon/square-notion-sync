"""Example: Square callout + Perplexity query + Comet ML logging

This file demonstrates a safe pattern:
- Read credentials from environment variables (never hardcode)
- Use Square sandbox by default for testing
- Optionally consult Perplexity (pseudo example) and log with Comet

Do NOT commit real secrets. Use a .env file for local dev or a secret manager in prod.
"""
import os
import json
import requests
from dotenv import load_dotenv

try:
    from perplexity import Perplexity
except Exception:
    Perplexity = None

try:
    from comet_ml import Experiment
except Exception:
    Experiment = None


load_dotenv()

SQUARE_ENV = os.getenv("SQUARE_ENV", "sandbox")
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")

if SQUARE_ENV == "sandbox":
    SQUARE_BASE = "https://connect.squareupsandbox.com"
    ACCESS_TOKEN = os.getenv("SQUARE_SANDBOX_ACCESS_TOKEN")
else:
    SQUARE_BASE = "https://connect.squareup.com"
    ACCESS_TOKEN = os.getenv("SQUARE_ACCESS_TOKEN")

PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")
COMET_KEY = os.getenv("COMET_API_KEY")


def call_square_payments(amount_cents=100, currency="USD"):
    """Example minimal Payments create request (won't run unless you provide valid token and set DRY_RUN=false)."""
    url = f"{SQUARE_BASE}/v2/payments"
    headers = {
        "Square-Version": "2025-11-11",
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    # Example body: using idempotency_key and placeholder source_id (in real world use a nonce from Square Web SDK)
    body = {
        "idempotency_key": "example-key-123",
        "source_id": "cnon:card-nonce-ok",
        "amount_money": {"amount": amount_cents, "currency": currency},
    }

    print("Prepared request to", url)
    if DRY_RUN:
        print("DRY_RUN enabled — skipping POST. Body:\n", json.dumps(body, indent=2))
        return {"status": "dry-run", "body": body}

    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()
    return resp.json()


def query_perplexity(prompt: str):
    """Example Perplexity usage — real usage depends on the installed client.
    This function will gracefully no-op if the Perplexity client isn't installed or configured.
    """
    if not PERPLEXITY_KEY or Perplexity is None:
        print("Perplexity not configured or client not installed — skipping.")
        return None

    # This is a placeholder pattern — adapt to your Perplexity client API
    client = Perplexity(api_key=PERPLEXITY_KEY)
    search = client.search.create(query=[prompt])
    results = []
    for r in search.results:
        results.append({"title": getattr(r, "title", None), "url": getattr(r, "url", None)})
    return results


def log_with_comet(metrics: dict, params: dict = None):
    if not COMET_KEY or Experiment is None:
        print("Comet not configured or client not installed — skipping logging.")
        return

    exp = Experiment(api_key=COMET_KEY, project_name="square-callouts")
    if params:
        exp.log_parameters(params)
    exp.log_metrics(metrics)
    exp.end()


def main():
    # Example flow
    print("Running square callout starter")
    # 1) Prepare/create payment (or dry-run)
    payment = call_square_payments(amount_cents=2500)
    print("Payment result:", payment)

    # 2) Ask Perplexity for context around Square or payments (optional)
    perplexity_out = query_perplexity("What are common edge cases when creating payments with Square API?")
    print("Perplexity out:", perplexity_out)

    # 3) Log a small experiment to Comet (optional)
    log_with_comet(metrics={"payment_dry_run": 1 if payment.get("status") == "dry-run" else 0}, params={"env": SQUARE_ENV})


if __name__ == "__main__":
    main()
