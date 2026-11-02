"""Externalizable Jade prompt, without copying private content into Git."""
from pathlib import Path
from src.utility.private_config import environ

def prompt_path(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[2]
    direct = str(environ("JADE_PROMPT_FILE", "")).strip()
    assets = str(environ("JADE_ASSETS_ROOT", "")).strip()
    if direct:
        return Path(direct).expanduser()
    if assets:
        return Path(assets).expanduser() / "prompts" / "chat.txt"
    return root / "prompt_chat.txt"

def load_prompt(project_root: Path | None = None) -> str:
    """An explicitly configured missing private prompt MUST NOT fall back."""
    try:
        content = prompt_path(project_root).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("Jade prompt asset missing or unreadable") from exc
    if not content.strip():
        raise ValueError("Jade prompt is empty")
    return content
