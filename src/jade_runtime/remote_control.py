"""Hidden, standalone Windows control plane for the Jade PyCharm Run session.

Tailscale Serve adds the /control path while the existing / route continues
to reach Jade's mobile gateway.  No shell commands or branch names arrive from
the phone; the PyCharm Run process is the *only* owner of Jade.
"""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import os
import subprocess
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler

from src.jade_runtime.session_logging import redact
from src.utility.private_config import environ

HERE = Path(__file__).resolve().parent
CONTROL_PAGE = HERE / "mobile_web" / "control.html"


class ControlService:
    def __init__(self, repo: Path, *, owner: str, origin: str,
                 mobile_token: str, ipc_token: str, log_dir: Path,
                 port: int = 8771, runner_port: int = 8772):
        origin_parts = urlsplit(origin)
        if (origin_parts.scheme != "https" or not (origin_parts.hostname or "").endswith(".ts.net")
                or origin_parts.path or origin_parts.query or origin_parts.fragment
                or origin.endswith("/")):
            raise ValueError("expected a private Tailscale HTTPS origin")
        if not owner or not owner.isascii() or len(owner) > 256:
            raise ValueError("invalid Tailscale login")
        if not all(isinstance(t, str) and 32 <= len(t) <= 256
                   for t in (mobile_token, ipc_token)):
            raise ValueError("missing private mobile/IPC credentials")
        self.repo = repo.resolve()
        self.owner = owner.casefold()
        self.origin = origin
        self.mobile_token, self.ipc_token = mobile_token, ipc_token
        self.log_dir = log_dir.resolve()
        self.port, self.runner_port = port, runner_port
        if not (1024 <= port <= 65535 and 1024 <= runner_port <= 65535
                and port != runner_port):
            raise ValueError("invalid ports")

    def runner_request(self, operation: str) -> tuple[int, dict]:
        if operation not in ("status", "update", "restart"):
            raise ValueError("unsupported IPC operation")
        request = Request(
            f"http://127.0.0.1:{self.runner_port}/{operation}", data=b"{}",
            method="POST", headers={"Authorization": "Bearer " + self.ipc_token,
                                    "Content-Type": "application/json"})
        try:
            with build_opener(ProxyHandler({})).open(request, timeout=3) as response:
                return response.status, json.load(response)
        except HTTPError as exc:
            return exc.code, {"error": "pycharm_runner_rejected"}
        except (URLError, OSError, ValueError):
            return 503, {"error": "pycharm_run_not_available"}

    def status(self) -> dict:
        code, state = self.runner_request("status")
        if code == 200:
            return state
        return {"pycharm_run": False, "running": False, "phase": "offline",
                "branch": "develop", "sha": None,
                "error": state.get("error", "pycharm_run_not_available")}

    def logs(self) -> str:
        path = self.log_dir / "jade-pycharm-console.log"
        try:
            with path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                length = handle.tell()
                handle.seek(max(0, length - 48_000))
                data = handle.read(48_000)
            # A byte-window can begin in the middle of a UTF-8 codepoint/line.
            lines = data.decode("utf-8", errors="replace").splitlines()
            if length > 48_000 and lines:
                lines = lines[1:]
            return redact("\n".join(lines[-150:]))
        except OSError:
            return ""

    def server(self) -> ThreadingHTTPServer:
        service = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                logging.info("admin_http %s", args[1] if len(args) > 1 else "request")

            def _path(self):
                path = self.path.split("?", 1)[0]
                if path == "/control":
                    return "/"
                return path.removeprefix("/control") or "/"

            def _identity_ok(self):
                return hmac.compare_digest(
                    self.headers.get("Tailscale-User-Login", "").casefold(),
                    service.owner)

            def _authorized(self):
                return hmac.compare_digest(
                    self.headers.get("Authorization", ""),
                    "Bearer " + service.mobile_token)

            def _origin_ok(self):
                return self.headers.get("Origin", "") == service.origin

            def do_GET(self):
                if not self._identity_ok():
                    return self._json(403, {"error": "tailscale_owner_required"})
                path = self._path()
                if path == "/":
                    try:
                        body = CONTROL_PAGE.read_bytes()
                    except OSError:
                        return self._json(503, {"error": "page_unavailable"})
                    return self._body(200, body, "text/html; charset=utf-8")
                if path not in ("/api/status", "/api/logs"):
                    return self._json(404, {"error": "not_found"})
                if not self._authorized():
                    return self._json(401, {"error": "mobile_token_required"})
                return self._json(200, service.status() if path.endswith("/status")
                                  else {"text": service.logs()})

            def do_POST(self):
                if not self._identity_ok():
                    return self._json(403, {"error": "tailscale_owner_required"})
                if not self._authorized():
                    return self._json(401, {"error": "mobile_token_required"})
                if not self._origin_ok():
                    return self._json(403, {"error": "invalid_origin"})
                path = self._path()
                if path not in ("/api/update", "/api/restart"):
                    return self._json(404, {"error": "not_found"})
                if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                    return self._json(400, {"error": "json_required"})
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    if length != 16:
                        # Exact JSON payload: {"confirm":true}, no branch.
                        return self._json(400, {"error": "confirmation_required"})
                    if json.loads(self.rfile.read(length)) != {"confirm": True}:
                        return self._json(400, {"error": "confirmation_required"})
                except (OSError, ValueError, UnicodeDecodeError):
                    return self._json(400, {"error": "invalid_request"})
                code, payload = service.runner_request(path.rsplit("/", 1)[1])
                return self._json(code, payload)

            def _json(self, code, data):
                return self._body(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                                  "application/json; charset=utf-8")

            def _body(self, code, body, content_type):
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return ThreadingHTTPServer(("127.0.0.1", self.port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hidden Jade control on Windows")
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    args.config.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=str(args.config.parent / "jade-control.log"),
                        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    repo = Path(config["repo"])
    if not (repo / "tools" / "jade_pycharm_runner.py").is_file():
        raise ValueError("configured Jade checkout missing")
    os.environ["JADE_SECRETS_FILE"] = config["secrets_file"]
    os.environ["JADE_PYCHARM_PRIVATE_DIR"] = config["private_dir"]
    # Reuse the actual PyCharm mobile credentials, never introduce a new account.
    from tools.jade_pycharm_runner import load_environment
    load_environment(os.environ)
    service = ControlService(
        repo, owner=os.environ["JADE_MOBILE_OWNER_LOGIN"],
        origin=os.environ["JADE_MOBILE_PUBLIC_ORIGIN"],
        mobile_token=os.environ["JADE_MOBILE_TOKEN"],
        ipc_token=str(environ("JADE_DEPLOY_SUPERVISOR_TOKEN", "")),
        log_dir=Path(os.environ["JADE_PYCHARM_PRIVATE_DIR"]) / "logs")
    try:
        server = service.server()
    except OSError as error:
        if error.errno in (48, 98, 10048) or getattr(error, "winerror", None) == 10048:
            logging.info("Jade controller already running on port %s", service.port)
            return
        raise
    logging.info("Jade controller started on loopback port %s", service.port)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Jade control could not start")
        raise
