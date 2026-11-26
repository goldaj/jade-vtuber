"""Generate an owner-only VAPID key pair for Jade's private Android PWA.

Requires pywebpush/py-vapid installed into Jade's Python environment.
Only the public applicationServerKey is printed; private PEM never leaves disk.
"""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import os

from cryptography.hazmat.primitives import serialization
from py_vapid import Vapid


def setup(directory: Path) -> tuple[Path, str]:
    directory = directory.expanduser().resolve()
    if not directory.is_absolute():
        raise ValueError("absolute private directory required")
    directory.mkdir(parents=True, exist_ok=True)
    private = directory / "jade-vapid-private.pem"
    if private.exists():
        raise FileExistsError(f"Existing VAPID secret: {private}. Reuse it; do not rotate.")
    vapid = Vapid()
    vapid.generate_keys()
    vapid.save_key(str(private))
    try:
        os.chmod(private, 0o600)
    except OSError:
        pass  # Windows: rely on the owner-only directory ACL.
    public_bytes = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    public_key = base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode("ascii")
    return private, public_key


def main():
    parser = argparse.ArgumentParser(description="Configure private Android Web Push")
    parser.add_argument("--directory", required=True, type=Path,
                        help="Absolute private folder on the PC, outside Git")
    args = parser.parse_args()
    private, public_key = setup(args.directory)
    print("Store the following values in Jade's private configuration:")
    print("JADE_PUSH_VAPID_PUBLIC_KEY=" + public_key)
    print("JADE_PUSH_VAPID_PRIVATE_KEY=" + str(private))
    print("JADE_PUSH_VAPID_SUBJECT=mailto:contact@example.invalid")
    print("Replace the mailto subject with a real contact address.")
    print("Never commit the private PEM. Keep these keys for future restarts.")


if __name__ == "__main__":
    main()
