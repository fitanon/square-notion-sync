from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from . import accounts
from . import notion_helper
from .oauth import router as oauth_router
from src.multi_account import SquareMultiAccount

app = FastAPI(
    title='FitAnon Square Sync API',
    description='Multi-account Square data sync for The Fit Clinic businesses',
    version='1.0.0'
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include OAuth routes
app.include_router(oauth_router)

# Initialize multi-account sync
sync_manager = SquareMultiAccount()


class SyncResult(BaseModel):
    status: str
    details: dict


class AccountStatus(BaseModel):
    name: str
    email: Optional[str]
    status: str
    locations: Optional[int]


@app.get('/health')
def health():
    return {
        'status': 'ok',
        'env': os.getenv('SQUARE_ENV', 'production'),
        'accounts_configured': len(sync_manager.accounts)
    }


@app.get('/accounts', response_model=List[AccountStatus])
def list_accounts():
    """List all configured Square accounts and their status."""
    summary = sync_manager.get_summary()
    return [
        AccountStatus(
            name=acc['name'],
            email=acc.get('email'),
            status=acc['status'],
            locations=acc.get('locations')
        )
        for acc in summary['accounts']
    ]


@app.get('/customers')
def get_all_customers():
    """Get customers from all accounts."""
    return sync_manager.get_all_customers()


@app.get('/customers/{source}')
def get_customers_by_source(source: str):
    """Get customers from a specific account."""
    if source not in sync_manager.accounts:
        raise HTTPException(status_code=404, detail=f'Account {source} not found')

    account = sync_manager.accounts[source]
    try:
        customers = account.get_all_customers()
        return {
            'source': source,
            'customers': customers,
            'count': len(customers)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get('/transactions')
def get_all_transactions(days: int = 30):
    """Get transactions from all accounts."""
    return sync_manager.get_all_transactions(days_back=days)


@app.get('/invoices')
def get_all_invoices():
    """Get invoices from all accounts."""
    return sync_manager.get_all_invoices()


@app.get('/summary')
def get_summary():
    """Get a summary of all accounts."""
    return sync_manager.get_summary()


@app.post('/sync/customer/{customer_id}', response_model=SyncResult)
def sync_customer(customer_id: str, account_name: str = None):
    """Fetch customer and related data from Square and attempt to upsert into Notion.

    If `NOTION_TOKEN` and `NOTION_DATABASE_ID` are set, the helper will attempt
    to create a page; otherwise the payload will be returned.
    """
    # Determine account token(s). For the prototype we read env vars like ACCOUNT__{NAME}__TOKEN
    if account_name:
        key = f'ACCOUNT__{account_name.upper()}__TOKEN'
        token = os.getenv(key)
        if not token:
            raise HTTPException(status_code=404, detail=f'Account token for {account_name} not found in env var {key}')
    else:
        # fall back to a default env var
        token = os.getenv('SQUARE_ACCESS_TOKEN')
        if not token:
            raise HTTPException(status_code=400, detail='No account_name provided and SQUARE_ACCESS_TOKEN not set')

    customer = accounts.get_customer(customer_id, token)
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found')

    last_payment = accounts.get_last_payment_for_customer(customer_id, token)
    orders = accounts.get_orders_for_customer(customer_id, token)
    bookings = []
    try:
        bookings = accounts.get_bookings_for_customer(customer_id, token)
    except Exception:
        # bookings may not be available on all accounts; ignore errors for prototype
        bookings = []

    payload = {
        'customer': customer,
        'last_payment': last_payment,
        'orders': orders,
        'bookings': bookings,
    }

    # Attempt Notion upsert (safe: prints payload if not configured)
    try:
        res = notion_helper.upsert_connection_row(customer.get('given_name', '') + ' ' + customer.get('family_name', ''), payload)
    except Exception as e:
        # return the payload and note the upsert error
        return {'status': 'partial', 'details': {'payload': payload, 'notion_error': str(e)}}

    return {'status': 'ok', 'details': {'payload': payload, 'notion_result': res}}


@app.post('/connect/oauth/callback')
def oauth_callback(code: str = None, state: str = None):
    # Placeholder: implement exchange of code for token and store mapping to account
    return {'status': 'not-implemented', 'code': code, 'state': state}
