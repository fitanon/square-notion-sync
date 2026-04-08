#!/usr/bin/env python3
"""FitAnon Square Sync CLI

Command-line interface for managing multi-account Square sync.

Usage:
    python cli.py status          # Check account status
    python cli.py customers       # List all customers
    python cli.py transactions    # List recent transactions
    python cli.py export          # Export all data to JSON
    python cli.py server          # Start the FastAPI server
    python cli.py sync            # Trigger a manual sync
"""

import sys
import json
import argparse
import logging
from datetime import datetime, timedelta

from core.config import Config
from core.accounts import MultiAccountClient


def get_client():
    """Initialize config and multi-account client."""
    config = Config.from_env()
    return MultiAccountClient(config), config


def cmd_status(args):
    """Check status of all connected accounts."""
    print("\n" + "=" * 60)
    print("  FitAnon Square Account Status")
    print("=" * 60)

    try:
        client, config = get_client()
    except Exception as e:
        print(f"\n  Error loading config: {e}")
        print("  Check your .env file.")
        return 1

    if not client.clients:
        print("\n  No accounts configured!")
        print("  Add tokens to .env file (see .env.example)")
        return 1

    for code, sq_client in client.clients.items():
        try:
            locations = list(sq_client.get_locations())
            print(f"\n  [✓] {code} — {sq_client.account.name}")
            print(f"      Locations: {len(locations)}")
            for loc in locations:
                print(f"        • {loc.get('name', 'Unknown')}")
        except Exception as e:
            print(f"\n  [✗] {code} — {sq_client.account.name}")
            print(f"      Error: {e}")

    print("\n" + "=" * 60)
    return 0


def cmd_customers(args):
    """List customers from all accounts."""
    print("\nFetching customers from all accounts...\n")
    client, config = get_client()

    account_counts = {}
    total = 0

    for customer in client.get_all_customers():
        code = customer.account_code
        if code not in account_counts:
            account_counts[code] = []
        account_counts[code].append(customer)
        total += 1

    for code, customers in account_counts.items():
        print(f"\n{'─' * 50}")
        print(f"  {code}: {len(customers)} customers")
        print(f"{'─' * 50}")

        if args.verbose:
            for i, c in enumerate(customers[:10]):
                print(f"    {i+1}. {c.full_name} — {c.email or 'N/A'}")
            if len(customers) > 10:
                print(f"    ... and {len(customers) - 10} more")

    print(f"\n{'=' * 50}")
    print(f"  TOTAL: {total} customers across {len(account_counts)} accounts")
    print(f"{'=' * 50}\n")
    return 0


def cmd_transactions(args):
    """List recent transactions from all accounts."""
    days = args.days or 30
    print(f"\nFetching transactions from last {days} days...\n")

    client, config = get_client()
    begin = datetime.utcnow() - timedelta(days=days)

    account_totals = {}
    total_amount = 0
    total_count = 0

    for payment in client.get_all_payments(begin_time=begin):
        code = payment.account_code
        if code not in account_totals:
            account_totals[code] = {"count": 0, "amount": 0, "payments": []}
        account_totals[code]["count"] += 1
        account_totals[code]["amount"] += payment.amount_cents
        account_totals[code]["payments"].append(payment)
        total_count += 1
        total_amount += payment.amount_cents

    for code, data in account_totals.items():
        print(f"\n{'─' * 50}")
        print(f"  {code}: {data['count']} transactions = ${data['amount'] / 100:,.2f}")
        print(f"{'─' * 50}")

        if args.verbose:
            for i, p in enumerate(data["payments"][:5]):
                print(f"    {i+1}. ${p.amount_cents / 100:.2f} — {p.status} — {p.created_at.strftime('%Y-%m-%d')}")
            if data["count"] > 5:
                print(f"    ... and {data['count'] - 5} more")

    print(f"\n{'=' * 50}")
    print(f"  TOTAL: {total_count} transactions = ${total_amount / 100:,.2f}")
    print(f"{'=' * 50}\n")
    return 0


def cmd_export(args):
    """Export all data to JSON files."""
    output_dir = args.output or "exports"
    import os
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\nExporting data to {output_dir}/...")

    client, config = get_client()

    # Export customers
    customers = [
        {"id": c.id, "account": c.account_code, "name": c.full_name, "email": c.email, "phone": c.phone}
        for c in client.get_all_customers()
    ]
    with open(f"{output_dir}/customers_{timestamp}.json", "w") as f:
        json.dump(customers, f, indent=2, default=str)
    print(f"  ✓ {len(customers)} customers exported")

    # Export transactions (last N days)
    days = args.days or 30
    begin = datetime.utcnow() - timedelta(days=days)
    payments = [
        {"id": p.id, "account": p.account_code, "amount": p.amount_cents / 100, "status": p.status, "date": str(p.created_at)}
        for p in client.get_all_payments(begin_time=begin)
    ]
    with open(f"{output_dir}/transactions_{timestamp}.json", "w") as f:
        json.dump(payments, f, indent=2, default=str)
    print(f"  ✓ {len(payments)} transactions exported ({days} days)")

    print(f"\n  All exports saved to {output_dir}/")
    return 0


def cmd_server(args):
    """Start the FastAPI server."""
    import subprocess
    port = args.port or 8000
    print(f"\nStarting API server on port {port}...")
    print(f"  API docs: http://localhost:{port}/docs")
    print(f"  Health:   http://localhost:{port}/health")
    print("\n  Press Ctrl+C to stop\n")

    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "api.app:create_app",
        "--factory",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload"
    ])
    return 0


def cmd_sync(args):
    """Trigger a manual sync to Notion."""
    from core.config import Config
    target = args.target or "all"

    config = Config.from_env()
    print(f"\nTriggering {target} sync...")

    if target in ("financial", "all"):
        from sync.financial import FinancialSync
        result = FinancialSync(config).sync()
        print(f"  Financial: {'✓' if result.success else '✗'} — {result.records_created} created, {result.records_updated} updated")

    if target in ("appointments", "all"):
        from sync.appointments import AppointmentsSync
        result = AppointmentsSync(config).sync()
        print(f"  Appointments: {'✓' if result.success else '✗'} — {result.records_created} created, {result.records_updated} updated")

    if target in ("sessions", "all"):
        from sync.sessions import SessionsSync
        result = SessionsSync(config).sync()
        print(f"  Sessions: {'✓' if result.success else '✗'} — {result.records_created} created, {result.records_updated} updated")

    print()
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="FitAnon Square Multi-Account Sync CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status
    sp = subparsers.add_parser("status", help="Check account connections")
    sp.set_defaults(func=cmd_status)

    # Customers
    sp = subparsers.add_parser("customers", help="List all customers")
    sp.add_argument("-v", "--verbose", action="store_true", help="Show details")
    sp.set_defaults(func=cmd_customers)

    # Transactions
    sp = subparsers.add_parser("transactions", help="List recent transactions")
    sp.add_argument("-v", "--verbose", action="store_true", help="Show details")
    sp.add_argument("-d", "--days", type=int, default=30, help="Days to look back")
    sp.set_defaults(func=cmd_transactions)

    # Export
    sp = subparsers.add_parser("export", help="Export data to JSON")
    sp.add_argument("-o", "--output", default="exports", help="Output directory")
    sp.add_argument("-d", "--days", type=int, default=30, help="Days for transactions")
    sp.set_defaults(func=cmd_export)

    # Server
    sp = subparsers.add_parser("server", help="Start FastAPI server")
    sp.add_argument("-p", "--port", type=int, default=8000, help="Port number")
    sp.set_defaults(func=cmd_server)

    # Sync
    sp = subparsers.add_parser("sync", help="Trigger manual Notion sync")
    sp.add_argument("target", nargs="?", default="all", choices=["financial", "appointments", "sessions", "all"])
    sp.set_defaults(func=cmd_sync)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
