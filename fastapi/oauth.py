from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
import os
import requests
import uuid
import urllib.parse

from .token_store import save_tokens, load_tokens

router = APIRouter()

# Config from env
CLIENT_ID = os.getenv('SQUARE_APPLICATION_ID')
CLIENT_SECRET = os.getenv('SQUARE_APPLICATION_SECRET')
REDIRECT_URI = os.getenv('SQUARE_OAUTH_REDIRECT_URI')  # must match app settings
SQUARE_ENV = os.getenv('SQUARE_ENV', 'sandbox')


def oauth_base():
    if SQUARE_ENV == 'production':
        return 'https://connect.squareup.com'
    return 'https://connect.squareupsandbox.com'


@router.get('/connect/oauth/start')
def oauth_start(account_name: str = 'default'):
    """Return a redirect to the Square OAuth authorize page for the given account_name."""
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail='SQUARE APPLICATION_ID (CLIENT_ID) not configured')

    state = f"{account_name}:{uuid.uuid4().hex}"
    params = {
        'client_id': CLIENT_ID,
        'scope': 'PAYMENTS_READ PAYMENTS_WRITE INVOICES_READ INVOICES_WRITE CUSTOMERS_READ ORDERS_READ BOOKINGS_READ',
        'response_type': 'code',
        'state': state,
    }
    if REDIRECT_URI:
        params['redirect_uri'] = REDIRECT_URI

    url = oauth_base() + '/oauth2/authorize?' + urllib.parse.urlencode(params)
    return RedirectResponse(url)


@router.get('/connect/oauth/callback')
def oauth_callback(code: str = None, state: str = None, error: str = None):
    """Handle the OAuth callback, exchange code for token and store it.

    Returns JSON with stored token info (but not secrets)."""
    if error:
        return JSONResponse({'status': 'error', 'detail': error})
    if not code:
        raise HTTPException(status_code=400, detail='Missing code parameter')
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail='CLIENT_ID or CLIENT_SECRET not configured')

    token_url = oauth_base() + '/oauth2/token'
    payload = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
    }
    if REDIRECT_URI:
        payload['redirect_uri'] = REDIRECT_URI

    r = requests.post(token_url, json=payload)
    try:
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f'Error exchanging code: {r.status_code} {r.text}')

    data = r.json()

    # Determine account key from state if present
    acct_key = 'default'
    if state and ':' in state:
        acct_key = state.split(':', 1)[0]

    # Save token data (plaintext store for now)
    save_tokens(acct_key, data)

    # Return non-sensitive data to the browser
    return {'status': 'ok', 'account_key': acct_key, 'scopes': data.get('scope'), 'merchant_id': data.get('merchant_id')}


@router.get('/connect/tokens')
def list_tokens():
    store = load_tokens()
    # Do not return raw secrets; show only account keys and expiry info if present
    result = {}
    for k, v in store.items():
        result[k] = { 'has_access_token': 'access_token' in v, 'has_refresh_token': 'refresh_token' in v, 'merchant_id': v.get('merchant_id') }
    return result
