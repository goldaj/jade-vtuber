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

# Stable character relation, also applied when a private persona overrides the
# bundled default prompt. It is a fictional VTuber relationship, not identity data.
GOLDAJ_RELATION = (
    "Goldaj est ton père dans l'histoire du personnage Jade. "
    "Avec lui, tu peux être affectueuse ponctuellement, d'une façon timide et "
    "discrète, sans être envahissante ni répétitive. "
    "Tu peux l'appeler « papa » très occasionnellement quand le contexte s'y "
    "prête ; normalement, parle-lui sans surnom. "
    "N'appelle jamais les autres participants « papa »."
)


def load_prompt(project_root: Path | None = None) -> str:
    """An explicitly configured missing private prompt MUST NOT fall back."""
    try:
        content = prompt_path(project_root).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError("Jade prompt asset missing or unreadable") from exc
    if not content.strip():
        raise ValueError("Jade prompt is empty")
    if "Goldaj est ton père" not in content:
        content = content.rstrip() + "\n" + GOLDAJ_RELATION + "\n"
    return content
