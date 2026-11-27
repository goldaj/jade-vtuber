"""Prepare the voice review packet offline; never open an audio session.

Usage: python scripts/live_voice_preview.py --name "Jade candidate 1"
The JSON includes the future creation request and a common French corpus. It is
preparation, not a created voice, a successful preview, or a selection decision.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.jade_runtime.live_voice import JADE_VOICE_PROMPT, prepare_voice_review


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Préparer hors ligne l’écoute comparative de la voix de Jade.")
    parser.add_argument("--name", default="Jade candidate 1", help="Nom de la candidate, sans créer de voix.")
    parser.add_argument("--prompt", default=JADE_VOICE_PROMPT, help="Description acoustique originale.")
    args = parser.parse_args(argv)
    try:
        packet = prepare_voice_review(args.name, args.prompt)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(packet, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
