"""Verify downloaded current Jade assets using only the Python standard library."""

import hashlib
import json
from pathlib import Path


def file_references(value, kind=''):
    if isinstance(value, str):
        yield kind, value
    elif isinstance(value, list):
        for item in value:
            yield from file_references(item, kind)
    elif isinstance(value, dict):
        for key, child in value.items():
            if key not in {'FadeInTime', 'FadeOutTime', 'Name', 'Group', 'Id'}:
                yield from file_references(child, key)


def verify():
    root = Path(__file__).resolve().parent
    repo = root.parent
    manifest = json.loads((root / 'ASSET_MANIFEST.json').read_text(encoding='utf-8-sig'))
    failures = []
    for entry in manifest:
        path = repo / entry['path']
        if not path.is_file():
            failures.append('Missing asset: ' + entry['path'])
            continue
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
        if path.stat().st_size != entry['bytes'] or digest.hexdigest() != entry['sha256']:
            failures.append('Hash or size mismatch: ' + entry['path'] + ' (run git lfs pull)')

    references = 0
    models = list(root.rglob('*.model3.json'))
    for model in models:
        data = json.loads(model.read_text(encoding='utf-8-sig'))
        for kind, name in file_references(data.get('FileReferences', {})):
            if kind in {'Moc', 'Textures', 'Physics', 'Pose', 'UserData', 'DisplayInfo', 'File', 'Sound'} and name:
                references += 1
                if not (model.parent / name.replace('\\', '/')).is_file():
                    failures.append('Missing model reference: ' + name)
    asset_suffixes = ('.motion3.json', '.exp3.json', '.physics3.json', '.pose3.json', '.moc3', '.model3.json', '.cdi3.json', '.png', '.jpg')
    def leaves(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for child in value:
                yield from leaves(child)
        elif isinstance(value, dict):
            for child in value.values():
                yield from leaves(child)
    for config in root.rglob('*.vtube.json'):
        data = json.loads(config.read_text(encoding='utf-8-sig'))
        for name in set(leaves(data)):
            if name.lower().endswith(asset_suffixes):
                references += 1
                resolved = config.parent / name.replace('\\', '/')
                if not resolved.is_file() and Path(name).name == name and name.lower().endswith(('.exp3.json', '.motion3.json')):
                    candidates = list(config.parent.rglob(name))
                    if len(candidates) == 1:
                        resolved = candidates[0]
                if not resolved.is_file():
                    failures.append('Missing VTube Studio reference: ' + name)
    result = {'manifest_files': len(manifest), 'model_packages': len(models), 'references_checked': references, 'failures': failures}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(verify())
