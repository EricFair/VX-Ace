"""Bounded PNG IHDR observations; never a full image decoder or repair tool."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import struct
import zlib
from vxace_index_query import unlinked

PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
TILESET_DIMENSIONS = ((512, 384), (512, 384), (512, 256), (512, 480),
                      (256, 512), (512, 512), (512, 512), (512, 512), (512, 512))


def png_header(raw):
    """Parse exactly the signature and first IHDR, without allocating pixel data."""
    if len(raw) != 33 or raw[:8] != PNG_SIGNATURE:
        raise ValueError('Missing or truncated PNG signature/IHDR')
    if raw[8:16] != b'\x00\x00\x00\x0dIHDR':
        raise ValueError('PNG first chunk must be a 13-byte IHDR')
    if zlib.crc32(raw[12:29]) & 0xffffffff != struct.unpack('>I', raw[29:33])[0]:
        raise ValueError('PNG IHDR checksum mismatch')
    width, height, depth, color, compression, filtering, interlace = struct.unpack('>IIBBBBB', raw[16:29])
    depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
    if not (0 < width < 2**31 and 0 < height < 2**31):
        raise ValueError('PNG dimensions outside the IHDR range')
    if depth not in depths.get(color, ()) or compression != 0 or filtering != 0 or interlace not in (0, 1):
        raise ValueError('Unsupported or malformed PNG IHDR fields')
    return {'format': 'png', 'width': width, 'height': height, 'bit_depth': depth,
            'color_type': color, 'interlace': interlace}


def read_header(path):
    """Read at most 33 bytes, rechecking path and descriptor metadata around it."""
    path = unlinked(path)
    if path.suffix.lower() != '.png':
        return {'status': 'unsupported_header_format'}, None
    before = path.stat()
    with path.open('rb') as handle:
        opened = os.fstat(handle.fileno())
        raw = handle.read(33)
        after = os.fstat(handle.fileno())
    unlinked(path)
    def stamp(value):
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns
    if not stamp(before) == stamp(opened) == stamp(after) == stamp(path.stat()):
        raise ValueError('Image changed during header read')
    digest = hashlib.sha256(raw).hexdigest()
    try:
        return {'status': 'header_observed', **png_header(raw)}, digest
    except ValueError as exc:
        return {'status': 'invalid_png_header', 'reason': str(exc)}, digest


def layout_checks(folder, name, header, tileset_slots=()):
    """Advisory default-engine layout checks; not engine loadability judgments."""
    if header.get('status') != 'header_observed':
        return []
    width, height = header['width'], header['height']
    checks = []
    if folder == 'Graphics/Characters':
        # Default RGSS3 tests the first two characters of the reference string,
        # not its basename. Nested paths do not gain basename-prefix semantics.
        single = len(name) >= 2 and name[0] in '!$' and '$' in name[:2]
        columns, rows = (3, 4) if single else (12, 8)
        fits = width >= columns and height >= rows and width % columns == 0 and height % rows == 0
        checks.append({'layout': 'single_character' if single else 'eight_characters',
                       'status': 'standard_layout' if fits else 'character_grid_remainder',
                       'columns': columns, 'rows': rows,
                       'default_frame_width': width // columns, 'default_frame_height': height // rows})
    if folder == 'Graphics/Tilesets':
        for slot in sorted(set(tileset_slots)):
            if type(slot) is not int or not 0 <= slot < 9:
                raise ValueError('Unsupported native tileset slot')
            expected = TILESET_DIMENSIONS[slot]
            checks.append({'layout': 'tileset', 'slot': slot,
                           'status': 'standard_layout' if (width, height) == expected else 'nonstandard_tileset_dimensions',
                           'standard_width': expected[0], 'standard_height': expected[1]})
    return checks
