"""Independent localhost Jade deployment supervisor for the private PWA.

Start this OUTSIDE the Jade runtime, from Windows Task Scheduler or a terminal.
It owns Jade's child process and survives a restart. HTTP never accepts shell
commands, repository paths, arbitrary URLs or unlisted branch names.
"""
from __future__ import annotations

import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}\Z")


def branch_valid(name):
    return (isinstance(name, str) and bool(BRANCH.fullmatch(name))
            and ".." not in name and "//" not in name and "@{" not in name
            and not name.endswith(("/", ".", ".lock")))


class Supervisor:
    def __init__(self, root: Path, command: list[str], *,
                 install_command: list[str] | None = None):
        root = root.resolve()
        if not (root / ".git").exists() or not command:
            raise ValueError("supervisor needs an existing Git checkout and start command")
        self.root = root
        self.command = list(command)
        self.install_command = list(install_command) if install_command else None
        self.child = None
        self.state = {"phase": "idle", "branch": None, "sha": None,
                      "error": None, "running": False}
        self.lock = threading.Lock()

    def git(self, *args, timeout=90):
        result = subprocess.run(["git", "-C", str(self.root), *args],
                                capture_output=True, text=True, timeout=timeout,
                                check=False)
        if result.returncode:
            raise RuntimeError("git_" + args[0] + "_failed")
        return result.stdout.strip()

    def branches(self):
        refs = self.git("for-each-ref", "--format=%(refname:short)",
                        "refs/remotes/origin/")
        return sorted(ref.removeprefix("origin/") for ref in refs.splitlines()
                      if ref.startswith("origin/")
                      and branch_valid(ref.removeprefix("origin/"))
                      and ref != "origin/HEAD")[:250]

    def snapshot(self):
        with self.lock:
            state = dict(self.state)
            state["running"] = (self.child is not None
                                and self.child.poll() is None)
        return state

    def _launch(self):
        self.child = subprocess.Popen(
            self.command, cwd=str(self.root), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.8)
        if self.child.poll() is not None:
            raise RuntimeError("jade_exited_on_start")

    def start(self):
        with self.lock:
            if self.child is not None and self.child.poll() is None:
                raise RuntimeError("jade_already_running")
            self._launch()
            self.state.update({"running": True,
                               "sha": self.git("rev-parse", "HEAD"),
                               "branch": self.git("branch", "--show-current") or "detached"})

    def request(self, *, branch=None, restart_only=False):
        if type(restart_only) is not bool or (not restart_only and not branch_valid(branch)):
            return False
        with self.lock:
            if self.state["phase"] != "idle":
                return False
            if self.child is None or self.child.poll() is not None:
                self.state["error"] = "jade_not_supervised"
                return False
            self.state.update({"phase": "working", "error": None})
        threading.Thread(target=self._perform, args=(branch, restart_only),
                         daemon=True, name="jade-supervisor-deployment").start()
        return True

    def _perform(self, branch, restart_only):
        previous_sha = None
        try:
            if not restart_only:
                if self.git("status", "--porcelain"):
                    raise RuntimeError("working_tree_not_clean")
                previous_sha = self.git("rev-parse", "HEAD")
                self.git("fetch", "--prune", "origin", timeout=180)
                if branch not in self.branches():
                    raise RuntimeError("unknown_remote_branch")
                target = self.git("rev-parse", "refs/remotes/origin/" + branch)
            else:
                target = self.git("rev-parse", "HEAD")
            old = self.child
            old.terminate()
            try:
                old.wait(timeout=20)
            except subprocess.TimeoutExpired:
                old.kill()
                old.wait(timeout=5)
            if not restart_only:
                self.git("switch", "--detach", target)
                if self.install_command is not None:
                    installed = subprocess.run(self.install_command, cwd=str(self.root),
                                               timeout=300, check=False)
                    if installed.returncode:
                        raise RuntimeError("install_failed")
            self._launch()
            with self.lock:
                self.state.update({"branch": branch if not restart_only
                                   else self.state["branch"],
                                   "sha": target, "running": True})
        except Exception as exc:
            # Do not leak paths, repository output, credentials or transcripts.
            if previous_sha is not None:
                try:
                    self.git("switch", "--detach", previous_sha)
                    if self.child is None or self.child.poll() is not None:
                        self._launch()
                except Exception:
                    pass
            with self.lock:
                self.state["error"] = (str(exc) if isinstance(exc, RuntimeError)
                                       else "deployment_failed")
                self.state["running"] = (self.child is not None
                                         and self.child.poll() is None)
        finally:
            with self.lock:
                self.state["phase"] = "idle"


def serve(supervisor, token: str, port: int):
    if not 32 <= len(token) <= 256 or not 1024 <= port <= 65535:
        raise ValueError("private supervisor token and localhost port required")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path not in ("/branches", "/status", "/deploy", "/restart"):
                return self.respond(404, {"error": "not_found"})
            if not hmac.compare_digest(self.headers.get("Authorization", ""),
                                       "Bearer " + token):
                return self.respond(401, {"error": "unauthorized"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 2 <= size <= 1024:
                    return self.respond(413, {"error": "size"})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    return self.respond(400, {"error": "body"})
            except (ValueError, UnicodeDecodeError):
                return self.respond(400, {"error": "json"})
            if self.path == "/branches" and data == {}:
                return self.respond(200, {"branches": supervisor.branches()})
            if self.path == "/status" and data == {}:
                return self.respond(200, supervisor.snapshot())
            if self.path == "/deploy" and set(data) == {"branch", "confirm"} and data["confirm"] is True:
                return self.respond(202 if supervisor.request(branch=data["branch"]) else 409,
                                    {"accepted": supervisor.snapshot()["phase"] == "working"})
            if self.path == "/restart" and data == {"confirm": True}:
                return self.respond(202 if supervisor.request(restart_only=True) else 409,
                                    {"accepted": supervisor.snapshot()["phase"] == "working"})
            return self.respond(400, {"error": "invalid_request"})

        def respond(self, code, payload):
            blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(blob)))
            self.end_headers()
            self.wfile.write(blob)

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8770)
    parser.add_argument("--start-json", required=True,
                        help="JSON argv array from trusted local configuration")
    parser.add_argument("--install-json", default=None,
                        help="Optional trusted JSON argv array for dependencies")
    args = parser.parse_args()
    command = json.loads(args.start_json)
    install = json.loads(args.install_json) if args.install_json else None
    if (not isinstance(command, list) or not command
            or any(not isinstance(x, str) or not x for x in command)
            or (install is not None and
                (not isinstance(install, list) or not install
                 or any(not isinstance(x, str) or not x for x in install)))):
        parser.error("start/install must be nonempty JSON argv string arrays")
    from src.utility.private_config import environ
    token = str(environ("JADE_DEPLOY_SUPERVISOR_TOKEN", ""))
    manager = Supervisor(args.root, command, install_command=install)
    manager.start()
    serve(manager, token, args.port)


if __name__ == "__main__":
    main()
