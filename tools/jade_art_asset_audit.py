"""Read-only duplicate inventory for Jade's artistic sources (OPS-015).

Outputs candidates and evidence only; never deletes, moves or rewrites assets.
Assets referenced dynamically or packed into CMO3/KRA/PSD may appear unreferenced,
so such entries require manual visual/artistic review before any cleanup.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from pathlib import Path

EXTS = {".cmo3", ".moc3", ".kra", ".psd", ".png", ".webp", ".jpg",
        ".jpeg", ".json", ".svg", ".clip", ".aseprite"}
SKIP = {".git", ".venv", "__pycache__", "node_modules"}
MAX_HASH_BYTES = 250_000_000


def audit(root: Path):
    root = root.resolve()
    sources = [root / "jade-modeling", root / "src/jade_runtime/mobile_web"]
    entries = []
    for source in sources:
        if not source.is_dir():
            continue
        for path in source.rglob("*"):
            if (not path.is_file() or path.is_symlink()
                    or any(part in SKIP for part in path.relative_to(root).parts)
                    or path.suffix.lower() not in EXTS):
                continue
            try:
                size = path.stat().st_size
                if size > MAX_HASH_BYTES:
                    digest = "too-large-to-hash"
                else:
                    h = hashlib.sha256()
                    with path.open("rb") as handle:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            h.update(block)
                    digest = h.hexdigest()
            except OSError:
                continue
            entries.append((path.relative_to(root).as_posix(), size, digest))
    buckets = defaultdict(list)
    for path, size, digest in entries:
        if digest != "too-large-to-hash":
            buckets[(size, digest)].append(path)
    exact = [sorted(paths) for paths in buckets.values() if len(paths) > 1]
    exact.sort(key=lambda xs: (-len(xs), xs[0]))
    stems = defaultdict(list)
    for path, _, _ in entries:
        stems[Path(path).stem.casefold()].append(path)
    related = [sorted(x) for x in stems.values() if len(x) > 1]
    related.sort(key=lambda xs: (-len(xs), xs[0]))
    return {"files": len(entries), "exact": exact, "similar_names": related}


def markdown(report):
    lines = ["# Audit lecture seule des assets Jade — OPS-015", "",
             f"Fichiers inspectés : **{report['files']}**.", "",
             "## Fichiers strictement identiques (SHA-256 + taille)", ""]
    if not report["exact"]:
        lines.append("Aucun doublon binaire détecté.")
    for group in report["exact"]:
        lines.append("- " + " ; ".join(f"`{p}`" for p in group))
    lines += ["", "## Noms communs (variantes ou exports possibles)", ""]
    if not report["similar_names"]:
        lines.append("Aucun nom commun.")
    for group in report["similar_names"][:100]:
        lines.append("- " + " ; ".join(f"`{p}`" for p in group))
    lines += ["", "**Décision :** conserver tous les fichiers avant revue manuelle "
              "des sources et références. Aucune suppression automatique autorisée.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(markdown(audit(args.root)))


if __name__ == "__main__":
    main()
