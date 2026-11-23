"""Launch the owner's local Discord/mobile test profile in PyCharm on Windows.

Private configuration is read on this PC, never embedded in the IDE project.
The Run tab owns one child runtime; debugger breakpoints are not preserved.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import ctypes
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODES = ("--live", "--voice", "--discord", "--discord-voice", "--avatar", "--mobile")
# Accepted flags mirror main.py. A user-owned PyCharm Run configuration may
# pass its exact modes through this wrapper rather than adopting the test preset.
MODE_FLAGS = (
    "--live", "--voice", "--mic", "--twitch", "--discord", "--vts",
    "--http", "--discord-voice", "--avatar", "--mobile", "--all-channels",
)


def selected_modes(argv: list[str]) -> tuple[bool, tuple[str, ...]]:
    """Return preflight-only and the requested Jade flags, preserving their order.

    The historical shared test configuration has no arguments; keep its
    existing preset. Explicit flags must never pick up an extra --avatar/mic.
    """
    parser = argparse.ArgumentParser(description="Profil PyCharm Jade géré à distance")
    parser.add_argument("--preflight-only", action="store_true")
    for flag in MODE_FLAGS:
        parser.add_argument(flag, action="store_true")
    args = parser.parse_args(argv)
    explicit = tuple(flag for flag in argv if flag in MODE_FLAGS)
    return args.preflight_only, explicit if explicit else MODES


class LaunchError(Exception):
    """A local setup problem, without private configuration values."""


def check_develop(root: Path) -> None:
    try:
        result = subprocess.run(["git", "-C", str(root), "branch", "--show-current"],
                                capture_output=True, text=True, timeout=10, check=True)
    except (OSError, subprocess.SubprocessError):
        raise LaunchError("Impossible de verifier la branche Git de Jade.") from None
    branch = result.stdout.strip()
    # Optional local-only recipe before merge; never enables mobile branch switching.
    test_ref = os.environ.get("JADE_PYCHARM_TEST_BRANCH", "").strip()
    if branch != "develop" and not (test_ref == branch
                                     and branch == "feat/jade-pycharm-remote-control-20261123"):
        raise LaunchError("Le test PyCharm de Jade exige develop (ou sa branche d'essai autorisée).")


def load_environment(env: dict[str, str], *, preserve_runtime: bool = False) -> None:
    """Load the owner's private mobile identity without leaking it.

    For a custom Run configuration preserve application-specific settings from
    the selected private .env instead of imposing the shared test profile.
    """
    private = Path(env.get("JADE_PYCHARM_PRIVATE_DIR", r"D:\Codex\private\jade-runtime"))
    config_path = private / "develop-mobile.json"
    token_path = private / "develop-mobile.token"
    secrets_path = Path(env.get("JADE_SECRETS_FILE", r"D:\Codex\private\jade-20261102\jade-actif-20261103.env"))
    try:
        config = json.loads(config_path.read_text(encoding="utf-8-sig"))
        token = token_path.read_text(encoding="utf-8-sig").strip()
        if (not secrets_path.is_file() or not isinstance(config, dict)
                or not isinstance(config.get("origin"), str) or not config["origin"]
                or not isinstance(config.get("owner"), str) or not config["owner"]
                or not token):
            raise ValueError
    except (OSError, ValueError, TypeError):
        raise LaunchError("Configuration privee Discord/mobile absente ou invalide sur ce PC.") from None

    if preserve_runtime:
        from src.utility.private_config import environ
        # Keep the caller's environment and the selected private .env as the
        # sources of truth. The profile's JSON/token are fallback values only.
        env.setdefault("PYTHONUTF8", "1")
        env.setdefault("PYTHONPYCACHEPREFIX", r"D:\\Codex\\caches\\python")
        env["JADE_SECRETS_FILE"] = str(secrets_path)
        defaults = {
            "JADE_MOBILE_ENABLED": "1",
            "JADE_MOBILE_PUBLIC_ORIGIN": config["origin"],
            "JADE_MOBILE_OWNER_LOGIN": config["owner"],
            "JADE_MOBILE_TOKEN": token,
            "JADE_MOBILE_PORT": "8766",
            "JADE_MOBILE_VENDOR_DIR": r"D:\\Jade\\private\\mobile-sdk",
        }
        for key, fallback in defaults.items():
            env.setdefault(key, str(environ(key, fallback)))
        # In particular do not force JADE_AUDIO_OUTPUT=none: the existing
        # 'discord & mobile' setup may play sound on the Windows host.
        ffmpeg = env.get("JADE_FFMPEG_DIR", r"D:\\Codex\\tools\\ffmpeg-2025-02-20\\bin")
        tailscale = env.get("JADE_TAILSCALE_DIR", r"D:\\Codex\\tools\\Tailscale")
        env["PATH"] = os.pathsep.join((ffmpeg, tailscale, env.get("PATH", "")))
        return

    env.update({
        "PYTHONUTF8": "1",
        "PYTHONPYCACHEPREFIX": env.get("PYTHONPYCACHEPREFIX", r"D:\Codex\caches\python"),
        "JADE_SECRETS_FILE": str(secrets_path),
        "JADE_AUDIO_OUTPUT": "none",
        "JADE_SUBTITLE_PATH": str(private / "subtitle.txt"),
        "JADE_MOBILE_ENABLED": "1",
        "JADE_MOBILE_PUBLIC_ORIGIN": config["origin"],
        "JADE_MOBILE_OWNER_LOGIN": config["owner"],
        "JADE_MOBILE_TOKEN": token,
        "JADE_MOBILE_PORT": "8766",
        "JADE_MOBILE_VENDOR_DIR": env.get("JADE_MOBILE_VENDOR_DIR", r"D:\Jade\private\mobile-sdk"),
    })
    ffmpeg = env.get("JADE_FFMPEG_DIR", r"D:\Codex\tools\ffmpeg-2025-02-20\bin")
    tailscale = env.get("JADE_TAILSCALE_DIR", r"D:\Codex\tools\Tailscale")
    env["PATH"] = os.pathsep.join((ffmpeg, tailscale, env.get("PATH", "")))


@contextmanager
def single_instance():
    """Use the same per-user mutex as the installed production launcher."""
    if os.name != "nt":
        raise LaunchError("Ce profil local PyCharm est prevu pour Windows.")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.ReleaseMutex.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.CreateMutexW(None, False, "Local\\JadeDevelopRuntime")
    if not handle:
        raise LaunchError("Impossible de verifier le verrou de Jade.")
    owned = False
    try:
        status = kernel.WaitForSingleObject(handle, 0)
        if status not in (0, 0x80):  # acquired or abandoned
            raise LaunchError("Jade develop est deja ouverte ou son verrou est indisponible.")
        owned = True
        yield
    finally:
        if owned:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def check_other_runtime() -> None:
    # Some older launch methods do not take the shared mutex. Match only their
    # established command lines, without printing process arguments or secrets.
    script = ("$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\"; "
              "$p | Where-Object { $_.CommandLine -match 'launch-latency\\.py|main\\.py.+--(?:all-channels|discord)' } "
              "| ForEach-Object { $_.ProcessId }")
    try:
        result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-Command", script],
                                capture_output=True, text=True, timeout=15, check=True)
        ids = {int(value) for value in result.stdout.split()}
    except (OSError, subprocess.SubprocessError, ValueError):
        raise LaunchError("Impossible de verifier les autres instances Jade.") from None
    if ids - {os.getpid()}:
        raise LaunchError("Ferme la precedente instance Jade avant ce test.")


@contextmanager
def technical_log(directory: Path):
    """Add a bounded private diagnostic log without recording conversation logs."""
    directory.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(directory / "jade-pycharm-diagnostics.log", maxBytes=5_000_000,
                                  backupCount=2, encoding="utf-8")
    handler.setLevel(logging.INFO)
    handler.addFilter(lambda record: (not (record.name == "jade.conversation"
                                           or record.name.startswith("jade.conversation."))
                                      and (record.levelno >= logging.WARNING or
                                           (record.name == "jade.discord" and
                                            record.getMessage() == "Discord voice reconnected"))))
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    discord_logger = logging.getLogger("jade.discord")
    previous_discord_level = discord_logger.level
    discord_logger.setLevel(logging.INFO)
    # Adding the file handler would otherwise disable logging.lastResort and
    # hide warnings from the existing PyCharm console when root has no handler.
    fallback = None
    if not root.handlers:
        fallback = logging.StreamHandler(sys.stderr)
        fallback.setLevel(logging.WARNING)
        root.addHandler(fallback)
    root.addHandler(handler)
    try:
        yield
    finally:
        root.removeHandler(handler)
        handler.close()
        discord_logger.setLevel(previous_discord_level)
        if fallback is not None:
            root.removeHandler(fallback)
            fallback.close()


def main() -> int:
    preflight_only, modes = selected_modes(sys.argv[1:])
    check_develop(ROOT)
    with single_instance():
        check_other_runtime()
        load_environment(os.environ, preserve_runtime=any(flag in MODE_FLAGS for flag in sys.argv[1:]))
        os.chdir(ROOT)
        preflight = subprocess.run([sys.executable, str(ROOT / "main.py"), "--preflight", *modes],
                                   check=False)
        if preflight.returncode or preflight_only:
            return preflight.returncode
        # The PyCharm Run tab stays alive while its single Jade child restarts.
        # Direct Python debugger breakpoints are intentionally not supported.
        from src.jade_runtime.remote_pycharm import PycharmManager
        from src.utility.private_config import environ
        token = str(environ("JADE_DEPLOY_SUPERVISOR_TOKEN", ""))
        log_dir = Path(os.environ.get("JADE_PYCHARM_PRIVATE_DIR", r"D:\Codex\private\jade-runtime")) / "logs"
        PycharmManager(ROOT, token, log_dir=log_dir, flags=modes).run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except LaunchError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from None
