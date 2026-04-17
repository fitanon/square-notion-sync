#!/usr/bin/env python3
"""
Small Square API examples to fetch Payments, Orders, Customers, Invoices, and Bookings.

Usage examples (zsh):

export SQUARE_ACCESS_TOKEN="sq0atp-REPLACE"
export SQUARE_ENV="sandbox" # or production
export SQUARE_API_VERSION="2025-06-16"

python3 scripts/square_examples.py payments --limit 10

This script is intentionally minimal: it demonstrates the requests and prints JSON to stdout.
"""

import os
import sys
import requests
import argparse
import json

SQUARE_ACCESS_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
SQUARE_ENV = os.getenv('SQUARE_ENV', 'sandbox')
SQUARE_API_VERSION = os.getenv('SQUARE_API_VERSION', '2025-06-16')

BASE = 'https://connect.squareupsandbox.com' if SQUARE_ENV == 'sandbox' else 'https://connect.squareup.com'

HEADERS = {
    'Authorization': f'Bearer {SQUARE_ACCESS_TOKEN}' if SQUARE_ACCESS_TOKEN else '',
    'Accept': 'application/json',
    'Square-Version': SQUARE_API_VERSION,
}


def fetch_payments(limit=20, begin_time=None, end_time=None):
    url = f"{BASE}/v2/payments"
    params = {'limit': limit}
    if begin_time:
        params['begin_time'] = begin_time
    if end_time:
        params['end_time'] = end_time
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()


def fetch_orders(location_id=None, limit=20):
    url = f"{BASE}/v2/orders/search"
    payload = {"limit": limit}
    if location_id:
        payload['query'] = {"filter": {"location_id": {"location_ids": [location_id]}}}
    resp = requests.post(url, headers={**HEADERS, 'Content-Type': 'application/json'}, json=payload)
    resp.raise_for_status()
    return resp.json()


def fetch_customers(cursor=None, limit=20):
    url = f"{BASE}/v2/customers"
    params = {'cursor': cursor} if cursor else {}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    return resp.json()


def fetch_invoices():
    url = f"{BASE}/v2/invoices"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def fetch_bookings():
    url = f"{BASE}/v2/bookings"
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('what', choices=['payments', 'orders', 'customers', 'invoices', 'bookings'])
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--location', help='Square location id for orders')
    parser.add_argument('--begin', help='begin_time ISO8601')
    parser.add_argument('--end', help='end_time ISO8601')
    args = parser.parse_args()

    if not SQUARE_ACCESS_TOKEN:
        print('WARNING: SQUARE_ACCESS_TOKEN not set; calls will fail unless provided.')

    try:
        if args.what == 'payments':
            out = fetch_payments(limit=args.limit, begin_time=args.begin, end_time=args.end)
        elif args.what == 'orders':
            out = fetch_orders(location_id=args.location, limit=args.limit)
        elif args.what == 'customers':
            out = fetch_customers()
        elif args.what == 'invoices':
            out = fetch_invoices()
        else:
            out = fetch_bookings()

        print(json.dumps(out, indent=2))
    except requests.HTTPError as e:
        print(f'HTTP error: {e.response.status_code}')
        sys.exit(1)
    except Exception:
        print('Error: operation failed')
        sys.exit(1)
