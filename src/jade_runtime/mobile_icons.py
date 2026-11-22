"""PWA icon rasterized from the owner-approved floral screenshot.

Source is an indexed PNG cropped from the approved image: two white/yellow
flowers, sage dress green, dark leaves and fine gold ornaments. 96px is enough
for Android launcher display; 192/512 variants are bilinearly upscaled without
extra runtime graphics dependencies or private network resources.

Only stdlib PNG indexed-8 decoding is needed. This function never reads user
configuration, the Jade memory database, or the browser session.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import math
import struct
import zlib

SOURCE = Path(__file__).resolve().parent / "mobile_web" / "icon-source-96.png"
SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    d_a, d_b, d_c = abs(p - a), abs(p - b), abs(p - c)
    if d_a <= d_b and d_a <= d_c:
        return a
    if d_b <= d_c:
        return b
    return c


@lru_cache(maxsize=1)
def _source_rgba() -> tuple[int, int, bytes]:
    data = SOURCE.read_bytes()
    if not data.startswith(SIGNATURE) or len(data) > 100_000:
        raise ValueError("invalid floral PNG source")
    pos, compressed, palette, alpha = len(SIGNATURE), bytearray(), b"", b""
    width = height = 0
    while pos + 12 <= len(data):
        length = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + length
        if end > len(data):
            raise ValueError("truncated floral PNG source")
        payload = data[pos + 8:end - 4]
        crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise ValueError("invalid floral PNG checksum")
        pos = end
        if kind == b"IHDR":
            width, height, depth, colour, compression, filtering, interlace = \
                struct.unpack(">IIBBBBB", payload)
            if (width, height, depth, colour, compression, filtering, interlace) != \
                    (96, 96, 8, 3, 0, 0, 0):
                raise ValueError("unexpected floral PNG format")
        elif kind == b"PLTE":
            palette = payload
        elif kind == b"tRNS":
            alpha = payload
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
    if not palette or width != 96 or height != 96:
        raise ValueError("floral PNG missing palette or header")
    raw = zlib.decompress(bytes(compressed))
    if len(raw) != height * (width + 1):
        raise ValueError("invalid floral PNG pixels")
    previous = bytearray(width)
    pixels = bytearray(width * height * 4)
    pos = 0
    for y in range(height):
        filter_type = raw[pos]
        pos += 1
        row = bytearray(raw[pos:pos + width])
        pos += width
        if filter_type > 4:
            raise ValueError("unexpected floral PNG filter")
        for x in range(width):
            left = row[x-1] if x else 0
            up = previous[x]
            up_left = previous[x-1] if x else 0
            predictor = (0 if filter_type == 0 else
                         left if filter_type == 1 else
                         up if filter_type == 2 else
                         (left + up) // 2 if filter_type == 3 else
                         _paeth(left, up, up_left))
            row[x] = (row[x] + predictor) & 255
            index = row[x]
            start = index * 3
            if start + 3 > len(palette):
                raise ValueError("invalid floral PNG palette index")
            offset = (y * width + x) * 4
            pixels[offset:offset+4] = (
                palette[start:start+3] +
                bytes((alpha[index] if index < len(alpha) else 255,)))
        previous = row
    return width, height, bytes(pixels)


@lru_cache(maxsize=2)
def icon_png(size: int) -> bytes:
    """Return a valid PNG matching Android's required 192 or 512 resolution."""
    if size not in (192, 512):
        raise ValueError("only PWA icon sizes 192 and 512 are supported")
    width, height, source = _source_rgba()
    raw = bytearray()
    for y in range(size):
        sy = (y + .5) * height / size - .5
        sy0 = max(0, min(height - 1, math.floor(sy)))
        sy1 = max(0, min(height - 1, sy0 + 1))
        fy = min(1.0, max(0.0, sy - sy0))
        raw.append(0)  # PNG unfiltered RGBA scanline
        for x in range(size):
            sx = (x + .5) * width / size - .5
            sx0 = max(0, min(width - 1, math.floor(sx)))
            sx1 = max(0, min(width - 1, sx0 + 1))
            fx = min(1.0, max(0.0, sx - sx0))
            pixels = [
                ((sy0 * width + sx0) * 4, (1 - fx) * (1 - fy)),
                ((sy0 * width + sx1) * 4, fx * (1 - fy)),
                ((sy1 * width + sx0) * 4, (1 - fx) * fy),
                ((sy1 * width + sx1) * 4, fx * fy),
            ]
            a = sum(source[offset + 3] * weight for offset, weight in pixels)
            rgb = [
                round(sum(source[offset + channel] * source[offset + 3] * weight
                          for offset, weight in pixels) / a) if a else 0
                for channel in range(3)
            ]
            raw.extend(bytes((*(max(0, min(255, component)) for component in rgb),
                              max(0, min(255, round(a))))))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (SIGNATURE + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _chunk(b"IEND", b""))
