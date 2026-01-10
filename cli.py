#!/usr/bin/env python3
"""FitAnon Square Sync CLI

Simple command-line interface for managing multi-account Square sync.

Usage:
    python cli.py status          # Check account status
    python cli.py customers       # List all customers
    python cli.py transactions    # List recent transactions
    python cli.py invoices        # List invoices
    python cli.py export          # Export all data to JSON
    python cli.py server          # Start the FastAPI server
"""

import sys
import json
import argparse
from datetime import datetime

from src.multi_account import SquareMultiAccount


def cmd_status(args):
    """Check status of all connected accounts."""
    print("\n" + "=" * 60)
    print("  FitAnon Square Account Status")
    print("=" * 60)

    sync = SquareMultiAccount()

    if not sync.accounts:
        print("\n  No accounts configured!")
        print("  Add tokens to .env file:")
        print("    ACCOUNT__FITCLINIC_LLC__TOKEN=your_token")
        print("    ACCOUNT__FITCLINIC__TOKEN=your_token")
        print("    ACCOUNT__FITNESSWITHMIKE__TOKEN=your_token")
        return 1

    summary = sync.get_summary()

    for account in summary["accounts"]:
        status_icon = "✓" if account["status"] == "connected" else "✗"
        print(f"\n  [{status_icon}] {account['name']}")
        print(f"      Email: {account.get('email', 'N/A')}")
        print(f"      Environment: {account.get('environment', 'N/A')}")
        if account["status"] == "connected":
            print(f"      Locations: {account.get('locations', 0)}")
        else:
            print(f"      Error: {account.get('error', 'Unknown')}")

    print("\n" + "=" * 60)
    return 0


def cmd_customers(args):
    """List customers from all accounts."""
    print("\nFetching customers from all accounts...\n")

    sync = SquareMultiAccount()
    results = sync.get_all_customers()

    total = 0
    for result in results:
        source = result["source"]
        count = result["count"]
        total += count

        print(f"\n{'─' * 50}")
        print(f"  {source}: {count} customers")
        print(f"{'─' * 50}")

        if result.get("error"):
            print(f"  Error: {result['error']}")
            continue

        if args.verbose and result["customers"]:
            for i, customer in enumerate(result["customers"][:10]):
                name = f"{customer.get('given_name', '')} {customer.get('family_name', '')}".strip()
                email = customer.get("email_address", "N/A")
                print(f"    {i+1}. {name} - {email}")
            if count > 10:
                print(f"    ... and {count - 10} more")

    print(f"\n{'=' * 50}")
    print(f"  TOTAL: {total} customers across {len(results)} accounts")
    print(f"{'=' * 50}\n")
    return 0


def cmd_transactions(args):
    """List recent transactions from all accounts."""
    days = args.days or 30
    print(f"\nFetching transactions from last {days} days...\n")

    sync = SquareMultiAccount()
    results = sync.get_all_transactions(days_back=days)

    total = 0
    total_amount = 0
    for result in results:
        source = result["source"]
        count = result["count"]
        total += count

        print(f"\n{'─' * 50}")
        print(f"  {source}: {count} transactions")
        print(f"{'─' * 50}")

        if result.get("error"):
            print(f"  Error: {result['error']}")
            continue

        source_amount = 0
        for txn in result["transactions"]:
            amount = txn.get("amount_money", {}).get("amount", 0) / 100
            source_amount += amount

        total_amount += source_amount
        print(f"  Total: ${source_amount:,.2f}")

        if args.verbose and result["transactions"]:
            for i, txn in enumerate(result["transactions"][:5]):
                amount = txn.get("amount_money", {}).get("amount", 0) / 100
                status = txn.get("status", "N/A")
                created = txn.get("created_at", "")[:10]
                print(f"    {i+1}. ${amount:.2f} - {status} - {created}")
            if count > 5:
                print(f"    ... and {count - 5} more")

    print(f"\n{'=' * 50}")
    print(f"  TOTAL: {total} transactions = ${total_amount:,.2f}")
    print(f"{'=' * 50}\n")
    return 0


def cmd_invoices(args):
    """List invoices from all accounts."""
    print("\nFetching invoices from all accounts...\n")

    sync = SquareMultiAccount()
    results = sync.get_all_invoices()

    total = 0
    for result in results:
        source = result["source"]
        count = result["count"]
        total += count

        print(f"\n{'─' * 50}")
        print(f"  {source}: {count} invoices")
        print(f"{'─' * 50}")

        if result.get("error"):
            print(f"  Error: {result['error']}")

    print(f"\n{'=' * 50}")
    print(f"  TOTAL: {total} invoices across {len(results)} accounts")
    print(f"{'=' * 50}\n")
    return 0


def cmd_export(args):
    """Export all data to JSON files."""
    output_dir = args.output or "exports"
    import os
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\nExporting data to {output_dir}/...")

    sync = SquareMultiAccount()

    # Export summary
    summary = sync.get_summary()
    with open(f"{output_dir}/summary_{timestamp}.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  ✓ Summary exported")

    # Export customers
    customers = sync.get_all_customers()
    with open(f"{output_dir}/customers_{timestamp}.json", "w") as f:
        json.dump(customers, f, indent=2)
    print(f"  ✓ Customers exported")

    # Export transactions
    transactions = sync.get_all_transactions(days_back=args.days or 30)
    with open(f"{output_dir}/transactions_{timestamp}.json", "w") as f:
        json.dump(transactions, f, indent=2)
    print(f"  ✓ Transactions exported")

    # Export invoices
    invoices = sync.get_all_invoices()
    with open(f"{output_dir}/invoices_{timestamp}.json", "w") as f:
        json.dump(invoices, f, indent=2)
    print(f"  ✓ Invoices exported")

    print(f"\n  All exports saved to {output_dir}/")
    return 0


def cmd_server(args):
    """Start the FastAPI server."""
    import subprocess
    port = args.port or 8000
    print(f"\nStarting FastAPI server on port {port}...")
    print(f"  API docs: http://localhost:{port}/docs")
    print(f"  Health: http://localhost:{port}/health")
    print("\n  Press Ctrl+C to stop\n")

    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "fastapi.app:app",
        "--host", "0.0.0.0",
        "--port", str(port),
        "--reload"
    ])
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="FitAnon Square Multi-Account Sync CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check account status")
    status_parser.set_defaults(func=cmd_status)

    # Customers command
    customers_parser = subparsers.add_parser("customers", help="List all customers")
    customers_parser.add_argument("-v", "--verbose", action="store_true", help="Show details")
    customers_parser.set_defaults(func=cmd_customers)

    # Transactions command
    txn_parser = subparsers.add_parser("transactions", help="List transactions")
    txn_parser.add_argument("-v", "--verbose", action="store_true", help="Show details")
    txn_parser.add_argument("-d", "--days", type=int, default=30, help="Days to look back")
    txn_parser.set_defaults(func=cmd_transactions)

    # Invoices command
    inv_parser = subparsers.add_parser("invoices", help="List invoices")
    inv_parser.add_argument("-v", "--verbose", action="store_true", help="Show details")
    inv_parser.set_defaults(func=cmd_invoices)

    # Export command
    export_parser = subparsers.add_parser("export", help="Export data to JSON")
    export_parser.add_argument("-o", "--output", default="exports", help="Output directory")
    export_parser.add_argument("-d", "--days", type=int, default=30, help="Days for transactions")
    export_parser.set_defaults(func=cmd_export)

    # Server command
    server_parser = subparsers.add_parser("server", help="Start FastAPI server")
    server_parser.add_argument("-p", "--port", type=int, default=8000, help="Port number")
    server_parser.set_defaults(func=cmd_server)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
