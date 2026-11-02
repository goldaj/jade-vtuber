import importlib

import requests

from src.utility import credentials
from src.utility.private_config import save_twitch_tokens

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"


def refresh_twitch_token():
    """Refresh Twitch credentials and save them in the private environment file."""
    payload = {
        "client_id": credentials.TWITCH_CLIENT_ID,
        "client_secret": credentials.TWITCH_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": credentials.TWITCH_REFRESH_TOKEN,
    }
    response = requests.post(TWITCH_TOKEN_URL, data=payload, timeout=30)
    if response.status_code == 200:
        new_tokens = response.json()
        new_access_token = new_tokens["access_token"]
        new_refresh_token = new_tokens.get("refresh_token", credentials.TWITCH_REFRESH_TOKEN)
        save_twitch_tokens(new_access_token, new_refresh_token)
        importlib.reload(credentials)
        return new_access_token

    # Error bodies can contain credentials; log only the HTTP status.
    print(f"Twitch token refresh failed (HTTP {response.status_code}).")
    return None
