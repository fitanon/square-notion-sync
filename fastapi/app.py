from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

from . import accounts
from . import notion_helper
from .oauth import router as oauth_router

app = FastAPI(title='Square → Notion Sync (prototype)')

# include oauth routes
app.include_router(oauth_router)


class SyncResult(BaseModel):
    status: str
    details: dict


@app.get('/health')
def health():
    return {'status': 'ok', 'env': os.getenv('SQUARE_ENV', 'sandbox')}


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
            raise HTTPException(status_code=404, detail='Account not configured')
    else:
        # fall back to a default env var
        token = os.getenv('SQUARE_ACCESS_TOKEN')
        if not token:
            raise HTTPException(status_code=400, detail='Account not configured')

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
    except Exception:
        # return the payload and note the upsert error
        return {'status': 'partial', 'details': {'payload': payload, 'notion_error': 'upsert failed'}}

    return {'status': 'ok', 'details': {'payload': payload, 'notion_result': res}}


@app.post('/connect/oauth/callback')
def oauth_callback(code: str = None, state: str = None):
    # Placeholder: implement exchange of code for token and store mapping to account
    return {'status': 'not-implemented', 'code': code, 'state': state}
