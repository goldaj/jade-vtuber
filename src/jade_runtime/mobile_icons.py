"""Generate tiny deterministic PWA icons with Python's standard library.

No copyrighted artwork, image download, graphics stack or files on disk.
The app uses vector style but browsers requiring PNG 192/512 are supported.
"""
from functools import lru_cache
import struct
import zlib


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + kind + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))


@lru_cache(maxsize=2)
def icon_png(size: int) -> bytes:
    if size not in (192, 512):
        raise ValueError("only PWA icon sizes 192 and 512 are supported")
    centre = size / 2
    half = size * .375
    inner = (size * .107) ** 2
    dot = (size * .046) ** 2
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)  # PNG filter type None.
        for x in range(size):
            dx, dy = abs(x - centre), abs(y - centre)
            radius2 = dx * dx + dy * dy
            if radius2 < dot:
                color = (245, 227, 255)
            elif radius2 < inner:
                color = (48, 36, 75)
            elif dx + dy < half:
                color = (213, 180, 239)
            else:
                color = (29, 23, 49)
            pixels.extend(color)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(pixels), level=9))
            + _chunk(b"IEND", b""))
