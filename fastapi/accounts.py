import os
import requests
from typing import Optional

def account_base_and_headers(token: str, api_version: str = '2025-06-16'):
    env = os.getenv('SQUARE_ENV', 'sandbox')
    base = 'https://connect.squareupsandbox.com' if env == 'sandbox' else 'https://connect.squareup.com'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Square-Version': api_version,
    }
    return base, headers


def get_customer(customer_id: str, token: str) -> Optional[dict]:
    base, headers = account_base_and_headers(token)
    url = f"{base}/v2/customers/{customer_id}"
    r = requests.get(url, headers=headers)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json().get('customer')


def find_customer_by_email(email: str, token: str) -> Optional[dict]:
    base, headers = account_base_and_headers(token)
    url = f"{base}/v2/customers/search"
    payload = {"query": {"filter": {"email_address": {"email_address": email}}}}
    r = requests.post(url, headers={**headers, 'Content-Type': 'application/json'}, json=payload)
    r.raise_for_status()
    results = r.json().get('customers', []) or r.json().get('results', [])
    # Search API returns different shapes; normalize
    if isinstance(results, list) and results:
        # if search returns objects with 'customer'
        first = results[0]
        if isinstance(first, dict) and 'customer' in first:
            return first['customer']
        return results[0]
    return None


def get_last_payment_for_customer(customer_id: str, token: str) -> Optional[dict]:
    base, headers = account_base_and_headers(token)
    url = f"{base}/v2/payments"
    params = {'customer_id': customer_id, 'sort_order': 'DESC', 'limit': 1}
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()
    payments = r.json().get('payments', [])
    return payments[0] if payments else None


def get_orders_for_customer(customer_id: str, token: str, limit: int = 10) -> list:
    base, headers = account_base_and_headers(token)
    url = f"{base}/v2/orders/search"
    payload = {"query": {"filter": {"customer_filter": {"customer_ids": [customer_id]}}}, "limit": limit}
    r = requests.post(url, headers={**headers, 'Content-Type': 'application/json'}, json=payload)
    r.raise_for_status()
    return r.json().get('orders', [])


def get_bookings_for_customer(customer_id: str, token: str) -> list:
    base, headers = account_base_and_headers(token)
    url = f"{base}/v2/bookings?customer_id={customer_id}"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    return r.json().get('bookings', [])
