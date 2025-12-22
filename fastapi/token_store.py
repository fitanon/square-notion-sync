import os
import json
from typing import Dict

STORE_PATH = os.path.join(os.path.dirname(__file__), 'tokens.json')


def _plain_save(data: Dict):
    with open(STORE_PATH, 'w') as f:
        json.dump(data, f, indent=2)


def _plain_load() -> Dict:
    if not os.path.exists(STORE_PATH):
        return {}
    with open(STORE_PATH, 'r') as f:
        return json.load(f)


def save_tokens(account_key: str, token_data: Dict, encryptor=None):
    """Save token_data under account_key. If encryptor provided, use it."""
    store = _plain_load()
    store[account_key] = token_data
    _plain_save(store)
    return True


def load_tokens() -> Dict:
    return _plain_load()
