"""Run the complete offline suite from an isolated, private code preview.

CI runs this as its own bounded job, so no second full suite is hidden inside
the repository's unit tests. Provider credentials and editable source paths
are excluded; output remains live for diagnosis.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

if __package__:
    from .jade_publication_export import ROOT, create_preview, tracked_paths
else:
    from jade_publication_export import ROOT, create_preview, tracked_paths


def preview_environment(directory: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("JADE_", "OPENAI_", "TWITCH_", "DISCORD_",
                                  "TAVILY_", "ELEVENLABS_"))
           and key != "BOT_NAME"}
    env["JADE_SECRETS_FILE"] = str(directory / "nonexistent-private.env")
    env["JADE_PREVIEW_CLOSURE_INNER"] = "1"
    env.pop("PYTHONPATH", None)
    return env


def isolated_test_command(source: Path, *, full_suite: bool) -> list[str]:
    # -I ignores PYTHONPATH; remove editable-install source paths as well.
    bootstrap = '''
import pathlib, sys, unittest
source = pathlib.Path(sys.argv[1]).resolve()
root = pathlib.Path.cwd().resolve()
sys.path[:] = [str(root)] + [p for p in sys.path if p and not pathlib.Path(p).resolve().is_relative_to(source)]
import src, tools.jade_ci_preflight as preflight
assert pathlib.Path(src.__file__).resolve().is_relative_to(root)
assert pathlib.Path(preflight.__file__).resolve().is_relative_to(root)
if sys.argv[2] == 'full':
    suite = unittest.defaultTestLoader.discover('tests')
else:
    sys.path.insert(0, str(root / 'tests'))
    suite = unittest.defaultTestLoader.loadTestsFromNames(
        ['test_jade_core', 'test_discord_switch', 'test_live_config'])
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful() or result.testsRun == 0)
'''
    return [sys.executable, "-I", "-X", "utf8", "-c", bootstrap, str(source),
            "full" if full_suite else "smoke"]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="jade-preview-tests-") as directory:
        parent = Path(directory)
        destination = parent / "preview"
        create_preview(ROOT, destination, tracked_paths(ROOT))
        print("Running the complete offline suite from the isolated preview", flush=True)
        try:
            result = subprocess.run(
                isolated_test_command(ROOT, full_suite=True), cwd=destination,
                env=preview_environment(parent), check=False, timeout=420)
        except subprocess.TimeoutExpired:
            print("Isolated preview test deadline exceeded", file=sys.stderr, flush=True)
            return 124
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
