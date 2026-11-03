"""Explicit, read-only Twitch user-token validation; never refresh credentials."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"


class TwitchTokenError(ValueError):
    """The token or its permissions cannot be used by the IRC connector."""


class TwitchTokenExpired(TwitchTokenError):
    """Twitch rejected a previously stored token with HTTP 401."""


class TwitchValidationUnavailable(RuntimeError):
    """Twitch could not validate the token; its validity remains unknown."""


@dataclass(frozen=True)
class TwitchIdentity:
    # The account name is personal data and should not appear in logs/repr.
    login: str = field(repr=False)
    can_send: bool = False


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch_metadata(token: str) -> dict:
    request = Request(VALIDATE_URL, headers={"Authorization": "OAuth " + token})
    try:
        with build_opener(_NoRedirect()).open(request, timeout=10) as response:
            payload = response.read(65537)
        if len(payload) > 65536:
            raise TwitchValidationUnavailable("Twitch validation response is too large")
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise TwitchValidationUnavailable("Unexpected Twitch validation response")
        return data
    except HTTPError as exc:
        if exc.code == 401:
            raise TwitchTokenExpired("Twitch token is invalid or expired") from None
        raise TwitchValidationUnavailable("Twitch validation failed") from None
    except (URLError, TimeoutError, OSError, UnicodeError, json.JSONDecodeError):
        raise TwitchValidationUnavailable("Twitch validation unavailable") from None


def validate_twitch_token(token: str, *, login: str = "", send_enabled: bool = False) -> TwitchIdentity:
    """Validate a user access token and safely derive its IRC login if omitted.

    Read-only request: never changes, refreshes, saves or prints any credentials.
    Twitch IRC requires chat:read, plus chat:edit when sending is enabled.
    Call via asyncio.to_thread from asynchronous application code.
    """
    token = token.strip()
    if token.lower().startswith("oauth:"):
        token = token[6:]
    if not token or any(c.isspace() for c in token):
        raise TwitchTokenError("Twitch access token required")
    data = _fetch_metadata(token)
    found = data.get("login")
    scopes = data.get("scopes")
    if not isinstance(found, str) or not re.fullmatch(r"[A-Za-z0-9_]{2,25}", found):
        raise TwitchTokenError("A Twitch user token with an account login is required")
    if not isinstance(scopes, list) or any(not isinstance(s, str) for s in scopes):
        raise TwitchValidationUnavailable("Unexpected Twitch validation response")
    if "chat:read" not in scopes:
        raise TwitchTokenError("Twitch token lacks chat:read")
    if send_enabled and "chat:edit" not in scopes:
        raise TwitchTokenError("Twitch token lacks chat:edit")
    if login and login.casefold() != found.casefold():
        raise TwitchTokenError("Configured Twitch login does not match token owner")
    return TwitchIdentity(login=found.lower(), can_send="chat:edit" in scopes)
