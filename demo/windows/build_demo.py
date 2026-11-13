"""Build a narrowly scoped, offline Windows demo ZIP in D:\\Codex."""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TMP = Path(r"D:\Codex\tmp")
OUTPUT = Path(r"D:\Codex\outputs\jade-demo")
MODEL = ROOT / "jade-modeling/runtime-installed/Jade_professional_r20_idle_complete"
PORTRAIT = ROOT / ("jade-modeling/assets/live2d/r21_professional_art/"
                   "master_v4_assets_v1/Jade_r21_master_v3_canvas_3840x4160.png")
MODEL_FILES = (
    "icon.jpg", "items_pinned_to_model.json", "Jade.cdi3.json", "Jade.moc3",
    "Jade.model3.json", "Jade.physics3.json", "Jade.vtube.json",
    "Jade_idle.motion3.json", "Jade_proof.motion3.json", "Jade_tracking_lost.motion3.json",
    "preview.png", "expressions/Angry.exp3.json", "expressions/Blink.exp3.json",
    "expressions/Sad.exp3.json", "expressions/Smile.exp3.json",
    "expressions/Surprised.exp3.json", "expressions/WinkL.exp3.json",
    "expressions/WinkR.exp3.json", "Jade.4096/texture_00.png", "Jade.4096/texture_01.png",
)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build():
    if sys.platform != "win32":
        raise RuntimeError("La construction doit s'exécuter sous Windows.")
    if not PORTRAIT.is_file() or PORTRAIT.stat().st_size < 1024:
        raise RuntimeError("Portrait absent ou objet Git LFS non récupéré.")
    for name in MODEL_FILES:
        path = MODEL / name
        if not path.is_file() or path.read_bytes().startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise RuntimeError(f"Ressource absente ou objet Git LFS non récupéré : {name}")
    TMP.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="jade-demo-", dir=TMP))
    print(f"Construction temporaire : {scratch}", flush=True)
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
               "--name", "Jade-demo", "--paths", str(ROOT),
               "--distpath", str(scratch / "dist"), "--workpath", str(scratch / "build"),
               "--specpath", str(scratch), "--add-data", f"{PORTRAIT};assets",
               str(HERE / "jade_demo.py")]
    env = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(Path(r"D:\Codex\caches\pyinstaller")))
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    stage = scratch / "dist" / "Jade-demo"
    for name in MODEL_FILES:
        target = stage / "modele-r20" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MODEL / name, target)
    shutil.copy2(HERE / "LISEZ-MOI.txt", stage)
    licenses = stage / "licences"
    licenses.mkdir()
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python.txt")
    shutil.copy2(Path(sys.base_prefix) / "tcl/tk8.6/license.terms", licenses / "Tk.txt")
    pyinstaller = importlib.metadata.distribution("pyinstaller")
    pyinstaller_license = next(p for p in pyinstaller.files if str(p).endswith("licenses/COPYING.txt"))
    shutil.copy2(pyinstaller.locate_file(pyinstaller_license), licenses / "PyInstaller.txt")
    entries = sorted(p for p in stage.rglob("*") if p.is_file())
    sums = "".join(f"{digest(path)}  {path.relative_to(stage).as_posix()}\n" for path in entries)
    (stage / "SHA256SUMS.txt").write_text(sums, encoding="utf-8", newline="\n")
    archive = OUTPUT / (scratch.name + ".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            package.write(path, Path("Jade-demo") / path.relative_to(stage))
    print(f"Archive : {archive}", flush=True)
    return archive


if __name__ == "__main__":
    build()
