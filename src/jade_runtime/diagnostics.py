"""Offline preflight: no provider calls, sockets, microphone capture or bills."""
from dataclasses import dataclass
from importlib.util import find_spec
from importlib import metadata
import os
from shutil import which


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


def _installed(module):
    try:
        return find_spec(module) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _discord_stack_ok():
    try:
        metadata.distribution("discord.py")
    except metadata.PackageNotFoundError:
        return False
    for package in ("discord", "py-cord", "nextcord", "disnake"):
        try:
            metadata.distribution(package)
        except metadata.PackageNotFoundError:
            continue
        return False
    return _installed("discord")


def inspect_environment(settings, *, live=False, voice=False, mic=False,
                        twitch=False, discord=False, vts=False,
                        discord_voice=False, http=False):
    """Return explicit diagnostics without connecting to any external service.

    Checks of installed packages, configured flags and presence of secrets are
    not a validation that paid APIs, audio or OAuth work in the real world.
    """
    checks = [Check("Configuration Jade", True, "Format vérifié localement")]
    selected = any((voice, mic, twitch, discord, vts, discord_voice, http))
    if selected and not live:
        checks.append(Check("Mode live", False,
                            "Les connecteurs nécessitent --live"))
    if live:
        checks.append(Check(
            "OpenAI API", bool(settings.api_key.strip())
            and settings.api_key.strip() != "example",
            "Présence d'une clé uniquement, sans appel ni affichage"))
        checks.append(Check("SDK OpenAI", _installed("openai"),
                            "Dépendance Python installée, API non testée"))
        from .assets import load_prompt
        try:
            load_prompt()
            prompt_ok = True
        except ValueError:
            prompt_ok = False
        checks.append(Check("Persona", prompt_ok, "Fichier lisible et non vide, contenu masqué"))
    if voice:
        parent = settings.subtitle_path.parent
        checks.append(Check("Sous-titres", parent.is_dir() and os.access(parent, os.W_OK),
                            "Dossier existant accessible en écriture, sans création de fichier"))
        if settings.audio_output == "ffplay":
            checks.append(Check(
                "Lecture locale WAV", which("ffplay") is not None,
                "ffplay sur PATH, périphérique audio non testé"))
        else:
            checks.append(Check("Lecture WAV", bool(discord_voice),
                                "Choisir JADE_AUDIO_OUTPUT=ffplay ou Discord vocal"))
    if mic:
        checks.append(Check("Capture microphone", _installed("sounddevice"),
                            "sounddevice installé, aucun enregistrement réalisé"))
    if twitch:
        checks.append(Check(
            "Twitch activé", settings.twitch_enabled
            and all((settings.twitch_oauth, settings.channel)),
            "Jeton et canal présents ; login déduit si absent, OAuth et IRC non testés"))
    if discord:
        checks.append(Check(
            "Discord activé", settings.discord_enabled and bool(settings.discord_token),
            "Jeton présent, permissions et serveur non testés"))
        checks.append(Check("SDK Discord", _discord_stack_ok(),
                            "discord.py installé sans pile Discord concurrente, connexion non tentée"))
    if discord_voice:
        checks.append(Check(
            "Discord vocal autorisé",
            discord and voice and settings.discord_voice_enabled
            and settings.discord_voice_channel > 0 and settings.discord_voice_consent
            and bool(settings.discord_voice_allowed_users),
            "Canal, participants autorisés et consentement déclarés ; accès réel non testé"))
        checks.append(Check("Transport vocal Discord", _installed("discord.ext.voice_recv")
                            and _installed("nacl"),
                            "PCM/codec installés, périphériques non testés"))
        checks.append(Check("FFmpeg Discord", which("ffmpeg") is not None,
                            "ffmpeg sur PATH, lecture non testée"))
    if vts:
        from .vtube_studio import _validate_url
        try:
            _validate_url(settings.vts_url)
            local_url = True
        except (ValueError, TypeError):
            local_url = False
        checks.append(Check(
            "VTube Studio autorisé",
            settings.vts_enabled and bool(settings.vts_token) and local_url,
            "Jeton présent et URL locale uniquement, Cubism/WS non testés"))
        checks.append(Check("WebSocket VTS", _installed("websockets"),
                            "Client installé, VTube Studio non contacté"))
    if http:
        checks.append(Check(
            "API web privée", settings.http_enabled
            and len(settings.http_token) >= 32
            and 1024 <= settings.http_port <= 65535,
            "Jeton >=32 caractères, service lié à 127.0.0.1"))
        checks.append(Check(
            "Tailscale (option téléphone)", which("tailscale") is not None,
            "Optionnel, configuration Serve / ACL non testées", required=False))
    return checks
