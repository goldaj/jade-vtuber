"""PyCharm Run-owned Jade process manager.

The Run configuration stays open while the child runtime is restarted.  This is
NOT a second background Jade installation: only PyCharm launches the child.
The separate, hidden Windows control service speaks to this localhost endpoint.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ctypes
from ctypes import wintypes
import hmac
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
import socket
import sys
import threading
import time
from uuid import uuid4

from src.jade_runtime.session_logging import redact

LOG = logging.getLogger("jade.pycharm.remote")
FLAGS = ("--live", "--voice", "--discord", "--discord-voice", "--avatar", "--mobile")


class GitRefusal(RuntimeError):
    """Git operation refused without changing the working tree."""


def git(root: Path, *args: str, timeout: int = 90) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False)
    if result.returncode:
        raise GitRefusal("git_" + args[0].replace("-", "_") + "_failed")
    return result.stdout.strip()


def plan_develop_update(root: Path) -> tuple[str, str]:
    """Fetch while Jade is running. Never change branches or discard local data."""
    if git(root, "branch", "--show-current") != "develop":
        raise GitRefusal("wrong_branch_expected_develop")
    if git(root, "status", "--porcelain"):
        raise GitRefusal("working_tree_not_clean")
    old = git(root, "rev-parse", "HEAD")
    git(root, "fetch", "origin", "develop", timeout=180)
    target = git(root, "rev-parse", "FETCH_HEAD")
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", old, target],
        capture_output=True, timeout=20, check=False)
    if result.returncode:
        raise GitRefusal("develop_not_fast_forward")
    return old, target


class _WindowsJob:
    """Kill child processes if PyCharm forcibly terminates the parent Run."""
    def __init__(self):
        self.handle = None
        if os.name != "nt":
            return
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]
        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount",
                         "OtherOperationCount", "ReadTransferCount",
                         "WriteTransferCount", "OtherTransferCount")]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BasicLimits),
                        ("IoInfo", IoCounters),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
        kernel.SetInformationJobObject.argtypes = (
            wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD)
        kernel.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.CreateJobObjectW(None, None)
        if not handle:
            raise OSError("cannot_create_windows_job")
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(
                handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            kernel.CloseHandle(handle)
            raise OSError("cannot_set_windows_job_limits")
        self.kernel, self.handle = kernel, handle

    def assign(self, child: subprocess.Popen) -> None:
        if self.handle is not None and not self.kernel.AssignProcessToJobObject(
                self.handle, wintypes.HANDLE(child._handle)):
            child.kill()
            child.wait(timeout=5)
            raise OSError("cannot_attach_jade_to_pycharm_job")

    def close(self) -> None:
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class PycharmManager:
    def __init__(self, root: Path, token: str, *, port: int = 8772,
                 log_dir: Path | None = None):
        if not 32 <= len(token) <= 256:
            raise ValueError("JADE_DEPLOY_SUPERVISOR_TOKEN must be 32-256 chars")
        self.root = root.resolve()
        self.token, self.port = token, port
        self.log_dir = Path(log_dir or self.root / "logs").resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "jade-pycharm-console.log"
        self.child: subprocess.Popen | None = None
        self.stop_file: Path | None = None
        self.job = _WindowsJob()
        self.commands: Queue[str] = Queue(maxsize=1)
        self.lock = threading.Lock()
        self.state = {"phase": "idle", "error": None, "sha": None,
                      "branch": "develop", "pid": None}
        self.file_handler = RotatingFileHandler(
            self.log_path, maxBytes=5_000_000, backupCount=2, encoding="utf-8")
        self.file_handler.setFormatter(logging.Formatter("%(message)s"))
        self.server: ThreadingHTTPServer | None = None

    def status(self) -> dict:
        with self.lock:
            state = dict(self.state)
        state["running"] = self.child is not None and self.child.poll() is None
        state["pycharm_run"] = True
        return state

    def request(self, operation: str) -> bool:
        if operation not in ("restart", "update"):
            return False
        with self.lock:
            if self.state["phase"] != "idle" or not self.commands.empty():
                return False
            # Failed children can be restarted using the same Run configuration.
            self.state.update(phase="queued", error=None)
            self.commands.put_nowait(operation)
        return True

    def _tee(self, process: subprocess.Popen) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            try:
                sys.stdout.write(line)
                sys.stdout.flush()
            except (OSError, UnicodeError):
                pass
            record = logging.LogRecord("jade.pycharm.console", logging.INFO, "",
                                       0, redact(line.rstrip("\r\n")), (), None)
            with self.lock:
                self.file_handler.handle(record)
        process.stdout.close()

    def _start_child(self) -> None:
        self.stop_file = self.log_dir / ("runner-stop-" + uuid4().hex + ".flag")
        env = dict(os.environ)
        env["JADE_RUNNER_STOP_FILE"] = str(self.stop_file)
        env["PYTHONUNBUFFERED"] = "1"
        child = subprocess.Popen(
            [sys.executable, "-u", str(self.root / "main.py"), *FLAGS],
            cwd=str(self.root), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1)
        try:
            self.job.assign(child)
        except Exception:
            if child.stdout:
                child.stdout.close()
            raise
        self.child = child
        threading.Thread(target=self._tee, args=(child,), daemon=True,
                         name="jade-pycharm-console-tee").start()
        with self.lock:
            self.state.update(error=None, pid=child.pid,
                              sha=git(self.root, "rev-parse", "HEAD"),
                              branch=git(self.root, "branch", "--show-current"))
        print("[Jade Control] Moteur lancé dans cette session PyCharm Run.", flush=True)

    def _stop_child(self) -> None:
        child = self.child
        if child is None or child.poll() is not None:
            return
        if self.stop_file:
            self.stop_file.touch(exist_ok=True)
        try:
            child.wait(timeout=20)
        except subprocess.TimeoutExpired:
            print("[Jade Control] Arrêt gracieux expiré, arrêt forcé.", flush=True)
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=False)
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)
        finally:
            if self.stop_file:
                self.stop_file.unlink(missing_ok=True)
        self.child = None

    def _wait_ready(self, timeout: float = 55.0) -> None:
        """Do not report success until the existing mobile gateway is listening."""
        port = int(os.environ.get("JADE_MOBILE_PORT", "8766"))
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if self.child is None or self.child.poll() is not None:
                raise RuntimeError("jade_exited_on_start")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.4):
                    return
            except OSError:
                time.sleep(0.4)
        raise RuntimeError("jade_mobile_gateway_not_ready")

    def _restart(self, operation: str) -> None:
        with self.lock:
            self.state["phase"] = "checking"
            self.state["error"] = None
        before = target = None
        try:
            changed_dependencies = False
            if operation == "update":
                before, target = plan_develop_update(self.root)
                if before != target:
                    changed_dependencies = bool(git(
                        self.root, "diff", "--name-only", before, target, "--",
                        "pyproject.toml", "poetry.lock"))
            with self.lock:
                self.state["phase"] = "stopping"
            self._stop_child()
            if operation == "update" and before != target:
                with self.lock:
                    self.state["phase"] = "updating"
                if (git(self.root, "branch", "--show-current") != "develop"
                        or git(self.root, "rev-parse", "HEAD") != before
                        or git(self.root, "status", "--porcelain")):
                    raise GitRefusal("checkout_changed_before_update")
                # Merge the vetted commit, never a mutable FETCH_HEAD from another fetch.
                git(self.root, "merge", "--ff-only", target, timeout=180)
                # LFS data is fetched only for the checked-out develop commit.
                git(self.root, "lfs", "pull", timeout=180)
                if changed_dependencies:
                    print("[Jade Control] Dépendances modifiées : synchronisation Poetry.", flush=True)
                    if sys.prefix == sys.base_prefix:
                        raise RuntimeError("pycharm_python_virtualenv_required")
                    # Poetry must update the exact venv used by the PyCharm Run parent.
                    poetry_env = dict(os.environ)
                    poetry_env["VIRTUAL_ENV"] = sys.prefix
                    install = subprocess.run(
                        ["poetry", "sync", "--only", "main", "-E", "all", "--no-interaction"],
                        cwd=str(self.root), env=poetry_env, stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace",
                        timeout=600, check=False)
                    if install.returncode:
                        print("[Jade Control] Poetry : " +
                              redact((install.stdout or "")[-3000:]), flush=True)
                        raise RuntimeError("poetry_sync_failed")
            with self.lock:
                self.state["phase"] = "starting"
            self._start_child()
            self._wait_ready()
            print("[Jade Control] " + ("Mise à jour et redémarrage" if operation == "update"
                                      else "Redémarrage") + " terminés.", flush=True)
        except Exception as exc:
            message = str(exc) if isinstance(exc, (GitRefusal, RuntimeError)) else type(exc).__name__
            print("[Jade Control] Échec : " + message, flush=True)
            # On a preflight/fetch failure, the original runtime was never stopped.
            if self.child is None or self.child.poll() is not None:
                try:
                    self._start_child()  # Restart current checkout, do not reset history.
                except Exception:
                    pass
            with self.lock:
                self.state["error"] = message
        finally:
            with self.lock:
                self.state["phase"] = "idle"

    def _server(self) -> ThreadingHTTPServer:
        manager = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                if self.path not in ("/status", "/restart", "/update"):
                    return self.reply(404, {"error": "not_found"})
                if not hmac.compare_digest(
                        self.headers.get("Authorization", ""),
                        "Bearer " + manager.token):
                    return self.reply(401, {"error": "unauthorized"})
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if size != 2 or self.rfile.read(size) != b"{}":
                        return self.reply(400, {"error": "invalid_body"})
                except (ValueError, OSError):
                    return self.reply(400, {"error": "invalid_body"})
                if self.path == "/status":
                    return self.reply(200, manager.status())
                op = self.path.lstrip("/")
                return self.reply(202 if manager.request(op) else 409,
                                  {"accepted": manager.status()["phase"] == "queued"})

            def reply(self, code, value):
                body = json.dumps(value, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return ThreadingHTTPServer(("127.0.0.1", self.port), Handler)

    def run(self) -> None:
        try:
            self.server = self._server()
            threading.Thread(target=self.server.serve_forever, daemon=True,
                             name="jade-pycharm-control-ipc").start()
            self._start_child()
            while True:
                try:
                    operation = self.commands.get(timeout=0.5)
                except Empty:
                    if self.child is not None and self.child.poll() is not None:
                        with self.lock:
                            self.state["pid"] = None
                            self.state["error"] = self.state["error"] or "jade_process_exited"
                        self.child = None
                    continue
                self._restart(operation)
        finally:
            self._stop_child()
            if self.server:
                self.server.shutdown()
                self.server.server_close()
            self.file_handler.close()
            self.job.close()
