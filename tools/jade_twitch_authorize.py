"""Interactive Twitch device authorization into a *new*, private file only.

Nothing happens on import. Never prints access/refresh tokens or HTTP bodies.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.jade_runtime.twitch_token import validate_twitch_token
from src.utility.private_config import environ

DEVICE_URL = "https://id.twitch.tv/oauth2/device"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
DEVICE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


class AuthorizationError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _post(url, params):
    request = Request(url, data=urlencode(params).encode("ascii"), method="POST")
    try:
        with build_opener(_NoRedirect()).open(request, timeout=15) as response:
            body = response.read(65537)
            status = response.status
    except HTTPError as exc:
        status = exc.code
        body = exc.read(65537)
    except (URLError, OSError, TimeoutError):
        raise AuthorizationError("Twitch est inaccessible ; aucun jeton modifié.") from None
    if len(body) > 65536:
        raise AuthorizationError("Réponse Twitch invalide ; aucun jeton modifié.")
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError):
        raise AuthorizationError("Réponse Twitch invalide ; aucun jeton modifié.") from None
    if not isinstance(data, dict):
        raise AuthorizationError("Réponse Twitch invalide ; aucun jeton modifié.")
    return status, data


def _private_file(path: Path):
    """Create empty exclusive file, set ACL before writing any token."""
    path = path.expanduser().resolve()
    if path.is_relative_to(ROOT) or any((parent / ".git").exists() for parent in path.parents):
        raise AuthorizationError("Choisir un emplacement hors de tout dépôt Git.")
    if not path.parent.is_dir():
        raise AuthorizationError("Le dossier privé doit déjà exister.")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError:
        raise AuthorizationError("Impossible de créer un nouveau fichier privé ; aucun fichier existant n'est écrasé.") from None
    try:
        if os.name == "nt":
            result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                    capture_output=True, text=True, check=True)
            row = next(csv.reader(io.StringIO(result.stdout)))
            sid = row[-1].strip()
            if not re.fullmatch(r"S-1-(?:\d+-)+\d+", sid):
                raise AuthorizationError("Impossible de vérifier les permissions privées.")
            subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r",
                            "*" + sid + ":(F)", "*S-1-5-18:(F)", "*S-1-5-32-544:(F)"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return path, os.fdopen(fd, "w", encoding="utf-8", newline="\n")
    except (OSError, subprocess.SubprocessError, StopIteration, csv.Error, AuthorizationError):
        os.close(fd)
        path.unlink(missing_ok=True)
        raise AuthorizationError("Impossible de protéger le fichier privé ; aucun jeton enregistré.") from None


def authorize(client_id, output, *, allow_send=False, post=_post, now=time.monotonic,
              sleep=time.sleep, prompt=print):
    if not client_id or not re.fullmatch(r"[A-Za-z0-9]+", client_id):
        raise AuthorizationError("Client Twitch absent ou invalide dans la configuration privée.")
    path, file = _private_file(Path(output))
    success = False
    try:
        scopes = "chat:read" + (" chat:edit" if allow_send else "")
        status, device = post(DEVICE_URL, {"client_id": client_id, "scopes": scopes})
        code = device.get("user_code")
        device_code = device.get("device_code")
        interval = device.get("interval")
        expires = device.get("expires_in")
        if (status != 200 or not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9-]{4,32}", code)
                or not isinstance(device_code, str) or not device_code
                or type(interval) is not int or not 1 <= interval <= 60
                or type(expires) is not int or not 1 <= expires <= 3600):
            raise AuthorizationError("Impossible de démarrer l'autorisation Twitch.")
        prompt("Ouvre https://www.twitch.tv/activate et saisis ce code temporaire : " + code)
        deadline = now() + expires
        while now() + interval < deadline:
            sleep(interval)
            status, result = post(TOKEN_URL, {"client_id": client_id, "scopes": scopes,
                                              "device_code": device_code, "grant_type": DEVICE_GRANT})
            if status == 200:
                access, refresh = result.get("access_token"), result.get("refresh_token")
                if not all(isinstance(x, str) and re.fullmatch(r"[A-Za-z0-9_-]{10,512}", x)
                           for x in (access, refresh)):
                    raise AuthorizationError("Réponse Twitch incomplète ; aucun jeton enregistré.")
                identity = validate_twitch_token(access, send_enabled=allow_send)
                file.write("TWITCH_TOKEN=" + access + "\nTWITCH_REFRESH_TOKEN=" + refresh
                           + "\nTWITCH_BOT_LOGIN=" + identity.login + "\n")
                file.flush()
                success = True
                return path
            if status in (400, 428) and result.get("message") == "authorization_pending":
                continue
            if status in (400, 429) and result.get("message") == "slow_down":
                interval = min(interval + 5, 60)
                continue
            raise AuthorizationError("Autorisation Twitch refusée ou expirée ; aucun jeton enregistré.")
        raise AuthorizationError("Autorisation Twitch expirée ; aucun jeton enregistré.")
    finally:
        file.close()
        if not success:
            path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Obtenir de nouveaux jetons Twitch dans un nouveau fichier privé.")
    parser.add_argument("--output", type=Path, required=True, help="Nouveau fichier hors de tout dépôt Git")
    parser.add_argument("--allow-send", action="store_true", help="Demander aussi la permission d'écrire dans le chat")
    args = parser.parse_args()
    try:
        authorize(str(environ("TWITCH_CLIENT_ID", "")), args.output, allow_send=args.allow_send)
    except (AuthorizationError, ValueError, RuntimeError):
        print("Autorisation non aboutie. Vérifie la configuration privée et réessaie ; aucun jeton n'a été affiché.")
        return 1
    print("Jetons enregistrés dans le nouveau fichier privé ; la configuration existante est inchangée.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
