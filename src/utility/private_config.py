"""Load private settings outside Git; environment variables take precedence."""

import os
from pathlib import Path

from decouple import Config, RepositoryEnv

from src.utility.public_profile import profile_default

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECRETS_FILE = Path.home() / "Documents" / "Codex-Private" / "ai-vtuber-project" / ".env"


def secrets_file():
    override = os.environ.get("JADE_SECRETS_FILE")
    if override:
        return Path(override).expanduser()
    if DEFAULT_SECRETS_FILE.is_file():
        return DEFAULT_SECRETS_FILE
    return PROJECT_ROOT / ".env"


def environ(name, default=""):
    """Use the process environment, then the selected private dotenv file."""
    if name in os.environ:
        return os.environ[name]
    # A public profile can only provide allowlisted non-secret defaults.
    # Private environment and external dotenv always take precedence.
    fallback = profile_default(name, default)
    path = secrets_file()
    if not path.is_file():
        return fallback
    return Config(RepositoryEnv(str(path)))(name, default=fallback)
