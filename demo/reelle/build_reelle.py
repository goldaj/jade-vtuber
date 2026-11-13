"""Build a Windows installer and ZIP from explicitly selected Jade resources.

Uses a dedicated build environment; never reads Jade's private configuration.
The application and renderer are separate one-directory PyInstaller builds so
the windowless UI can start a console renderer with redirected stdin/stdout.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MODEL = ROOT / "jade-modeling/runtime-installed/Jade_professional_r20_idle_complete"
PROMPT = ROOT / "prompt_chat.txt"
TMP = Path(r"D:\Codex\tmp")
OUTPUT = Path(r"D:\Codex\outputs\jade-demo")
CACHE = Path(r"D:\Codex\caches\pyinstaller-reelle")
ISCC = Path(r"D:\Codex\tools\InnoSetup-7.1.1\ISCC.exe")

# Deliberately exclude every other repository file, including configuration.
MODEL_FILES = (
    "icon.jpg", "items_pinned_to_model.json", "Jade.cdi3.json", "Jade.moc3",
    "Jade.model3.json", "Jade.physics3.json", "Jade.vtube.json",
    "Jade_idle.motion3.json", "Jade_proof.motion3.json", "Jade_tracking_lost.motion3.json",
    "preview.png", "expressions/Angry.exp3.json", "expressions/Blink.exp3.json",
    "expressions/Sad.exp3.json", "expressions/Smile.exp3.json",
    "expressions/Surprised.exp3.json", "expressions/WinkL.exp3.json",
    "expressions/WinkR.exp3.json", "Jade.4096/texture_00.png", "Jade.4096/texture_01.png",
)

LICENSE_DISTRIBUTIONS = (
    "pyinstaller", "live2d-py", "pygame", "PyOpenGL", "Pillow", "numpy",
    "openai", "sounddevice", "python-decouple", "python-dotenv", "httpx",
    "httpcore", "httpx2", "httpcore2", "truststore", "pydantic", "pydantic-core", "certifi", "anyio", "sniffio",
    "typing-extensions", "idna", "h11", "jiter", "distro", "tqdm", "cffi",
    "pycparser", "annotated-types", "typing-inspection", "websockets", "packaging", "altgraph",
    "pefile", "pywin32-ctypes", "pyinstaller-hooks-contrib",
)
PRIVATE_KEY = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def copy_checked(source: Path, target: Path, root: Path) -> None:
    if not source.is_file() or not source.resolve().is_relative_to(root.resolve()):
        raise RuntimeError("Ressource absente ou située hors de sa racine attendue")
    with source.open("rb") as fp:
        if fp.read(50).startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError("Objet Git LFS absent : exécuter git lfs pull")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256(source) != sha256(target):
        raise RuntimeError("La copie d'une ressource ne correspond pas à l'original")


def copy_public_prompt(target: Path) -> None:
    """Package the tracked Jade personality only after a conservative scan."""
    if not PROMPT.is_file() or PROMPT.stat().st_size > 50_000:
        raise RuntimeError("Prompt Jade absent ou de taille inattendue")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.jade_publication_audit import scan_text
    try:
        content = PROMPT.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise RuntimeError("Prompt Jade impossible à lire") from None
    if not content.strip() or scan_text(content):
        raise RuntimeError("Prompt Jade vide ou potentiellement sensible")
    copy_checked(PROMPT, target, ROOT)


def source_is_notice(entry: Path) -> bool:
    """Exclude module bytecode and executables even under a licenses package."""
    return entry.suffix.casefold() not in {
        ".py", ".pyc", ".pyo", ".pyd", ".so", ".dll", ".exe", ".o", ".a",
    }


def copy_licenses(target: Path) -> None:
    """Include the license files distributed with the installed dependencies."""
    target.mkdir(parents=True, exist_ok=True)
    for name in LICENSE_DISTRIBUTIONS:
        try:
            dist = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            continue  # Some are platform-specific or not part of this environment.
        out = target / re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        for entry in dist.files or ():
            name_lower = entry.name.casefold()
            in_metadata = any(part.casefold().endswith(".dist-info") for part in entry.parts)
            # A package may contain a Python module named ``licenses`` (for
            # example packaging.licenses), with generated .pyc in an external
            # cache. Only metadata license directories or clearly named notice
            # files are licenses; do not package executable code as a notice.
            in_license_dir = (in_metadata and
                              any(part.casefold() == "licenses" for part in entry.parts))
            license_file = (in_license_dir or name_lower.startswith(
                ("license", "copying", "copyright"))) and source_is_notice(entry)
            if not license_file and not (in_metadata and name_lower == "metadata"):
                continue
            source = Path(dist.locate_file(entry))
            if source.is_file():
                if not source.resolve().is_relative_to(Path(dist.locate_file("")).resolve()):
                    raise RuntimeError("Licence située hors du paquet installé")
                # Preserve filenames under each distribution; never copy the package tree.
                out.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, out / source.name)
    pygame_license = HERE / "licenses/pygame-LGPL-2.1.txt"
    if (not pygame_license.is_file() or sha256(pygame_license) !=
            "a190dc9c8043755d90f8b0a75fa66b9e42d4af4c980bf5ddc633f0124db3cee7"):
        raise RuntimeError("La licence pygame attendue est absente ou modifiée")
    (target / "pygame").mkdir(exist_ok=True)
    shutil.copyfile(pygame_license, target / "pygame/LGPL-2.1.txt")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    tk_license = Path(sys.base_prefix) / "tcl/tk8.6/license.terms"
    tcl_license = Path(sys.base_prefix) / "tcl/tcl8.6/license.terms"
    for source, name in ((python_license, "Python.txt"), (tk_license, "Tk.txt"),
                         (tcl_license, "Tcl.txt")):
        if source.is_file():
            shutil.copyfile(source, target / name)
    (target / "Live2D-SDK.txt").write_text(
        "Le rendu utilise le SDK Live2D Cubism. Conditions du SDK et de publication :\n"
        "https://www.live2d.com/en/sdk/license/\n"
        "Le paquet live2d-py fournit sa licence distincte dans ce répertoire.\n",
        encoding="utf-8",
    )


def check_stage(stage: Path) -> None:
    """Reject common private files and PEM private keys before packaging."""
    count = 0
    for path in stage.rglob("*"):
        if not path.is_file():
            continue
        count += 1
        relative = path.relative_to(stage)
        low = path.name.casefold()
        if (any(part.casefold() == ".git" for part in relative.parts)
                or low == ".env" or low.startswith(".env.")
                or low in {"id_rsa", "id_ed25519"}
                or path.suffix.casefold() in {".key", ".p12", ".pfx", ".kdbx"}):
            raise RuntimeError("Un fichier privé interdit est présent dans le paquet")
        # Bytes are examined in bounded chunks; no sensitive content is printed.
        with path.open("rb") as fp:
            previous = b""
            while chunk := fp.read(1024 * 1024):
                joined = previous + chunk
                if PRIVATE_KEY.search(joined):
                    raise RuntimeError("Une clé privée PEM est présente dans le paquet")
                previous = joined[-128:]
    if not count:
        raise RuntimeError("Paquet vide")


def build_env() -> dict[str, str]:
    # Do not pass credentials from the owner's development environment to hooks.
    omitted = ("JADE_", "OPENAI_", "TWITCH_", "DISCORD_", "ELEVENLABS_")
    sensitive = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API_?KEY|ACCESS_?KEY|PRIVATE_?KEY", re.I)
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(omitted) and not sensitive.search(k)}
    env.update(TEMP=str(TMP), TMP=str(TMP), PYINSTALLER_CONFIG_DIR=str(CACHE),
               PIP_CACHE_DIR=r"D:\Codex\caches\pip", PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def freeze(name: str, scratch: Path, resources: Path, *, windowed: bool) -> Path:
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
               "--windowed" if windowed else "--console", "--onedir", "--name", name,
               "--paths", str(ROOT), "--distpath", str(scratch / "dist"),
               "--workpath", str(scratch / ("work-" + name)), "--specpath", str(scratch),
               "--collect-all", "live2d", "--collect-all", "sounddevice",
               "--collect-submodules", "pygame", "--collect-submodules", "OpenGL",
               "--collect-submodules", "websockets",
               "--hidden-import", "demo.reelle.avatar"]
    if windowed:
        command.extend(["--add-data", f"{resources / 'prompt_chat.txt'};assets"])
    else:
        command.extend(["--add-data", f"{resources / 'model'};assets/model"])
    command.append(str(HERE / "app.py"))
    subprocess.run(command, cwd=ROOT, env=build_env(), check=True)
    result = scratch / "dist" / name
    if not (result / (name + ".exe")).is_file():
        raise RuntimeError("PyInstaller n'a pas produit l'exécutable attendu")
    return result


def build() -> Path:
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise RuntimeError("La construction exige Windows 64 bits et Python 64 bits")
    for package in ("pyinstaller", "live2d-py", "pygame", "PyOpenGL", "Pillow",
                    "openai", "sounddevice", "python-decouple", "websockets"):
        try:
            importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"Dépendance de construction absente : {package}") from exc
    for required in (HERE / "app.py", HERE / "avatar.py", HERE / "session.py", ISCC):
        if not required.is_file():
            raise RuntimeError(f"Fichier nécessaire absent : {required.name}")
    for directory in (TMP, OUTPUT, CACHE):
        directory.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="jade-reelle-", dir=TMP))
    resources = scratch / "resources"
    for name in MODEL_FILES:
        copy_checked(MODEL / name, resources / "model" / name, MODEL)
    copy_public_prompt(resources / "prompt_chat.txt")

    gui = freeze("Jade", scratch, resources, windowed=True)
    renderer = freeze("Jade-renderer", scratch, resources, windowed=False)
    shutil.copytree(renderer, gui / "renderer")
    if not (gui / "renderer/_internal/assets/model/Jade.moc3").is_file():
        raise RuntimeError("Le modèle n'est pas présent dans le moteur du rendu")
    # PyInstaller imports can differ from the build environment. This smoke
    # verifies the frozen OpenAI, audio and WebSocket imports without opening
    # a connection or using the microphone/speakers. Fail the build if missing.
    subprocess.run([str(gui / "Jade.exe"), "--dependencies-smoke-test"],
                   cwd=gui, env=build_env(), timeout=30, check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    copy_licenses(gui / "licences")
    shutil.copyfile(HERE / "README-BUILD.md", gui / "NOTICE-CONSTRUCTION.md")
    # A separate public user guide is required, never copy arbitrary project docs.
    guide = HERE / "GUIDE-DEMO.md"
    if not guide.is_file():
        raise RuntimeError("Tutoriel public GUIDE-DEMO.md manquant")
    shutil.copyfile(guide, gui / "GUIDE-DEMO.md")
    check_stage(gui)
    installer_dir = scratch / "installer"
    installer_dir.mkdir()
    subprocess.run([str(ISCC), f"/DStagePath={gui}", f"/O{installer_dir}",
                    str(HERE / "setup.iss")], cwd=ROOT, env=build_env(), check=True)
    installer = installer_dir / "Installer-Jade.exe"
    if not installer.is_file():
        raise RuntimeError("L'installateur attendu n'a pas été produit")

    # Unique scratch-derived name avoids overwriting an existing deliverable.
    archive = OUTPUT / (scratch.name + ".zip")
    digest = sha256(installer)
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        package.write(installer, "Installer-Jade.exe")
        package.write(guide, "GUIDE-DEMO.md")
        package.writestr("SHA256SUMS.txt", digest + "  Installer-Jade.exe\n")
    print("Archive :", archive, flush=True)
    print("SHA-256 installateur :", digest, flush=True)
    return archive


if __name__ == "__main__":
    build()
