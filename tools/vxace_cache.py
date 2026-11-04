#!/usr/bin/env python3
"""Content-addressed result cache for the read-only decode and round-trip gates (v2.0).

Off unless the environment variable VXACE_CACHE_DIR names a directory (recipes set it to a folder inside their own
work directory and delete it at the end). Every key is a SHA-256 over the exact input bytes plus the exact tool that
produced the result (tool file hash, mode, interpreter), so a changed file, tool or interpreter can never hit an old
entry. Only deterministic results are stored: bridge decodes, mutator inspections and *passing* round trips.
A failed gate is never cached, so a refusal is always re-checked from the real bytes.
"""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path

VERSION = '1.0.0'
ENV = 'VXACE_CACHE_DIR'


def directory():
    value = os.environ.get(ENV)
    return Path(value) if value else None


def file_sha256(path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def tool_identity(path) -> str:
    """Hash of a tool file; a Python tool also covers the vendored codec next to it (tools/_vendor)."""
    path = Path(path)
    parts = [file_sha256(path)]
    vendor = path.resolve().parent / '_vendor'
    if path.suffix == '.py' and vendor.is_dir():
        parts += [file_sha256(f) for f in sorted(vendor.rglob('*.py'))]
    return key(*parts)


def key(*parts) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(str(part).encode('utf-8'))
        h.update(b'\0')
    return h.hexdigest()


def _path(kind, digest):
    root = directory()
    return root / kind / digest[:2] / (digest + '.bin') if root else None


def get(kind, digest):
    """Return cached bytes or None (also None when caching is off or the entry is unreadable)."""
    path = _path(kind, digest)
    if path is None:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def put(kind, digest, data: bytes):
    path = _path(kind, digest)
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix('.tmp%d' % os.getpid())
        temp.write_bytes(data)
        os.replace(temp, path)
    except OSError:
        pass  # a cache that cannot write is just a slower run


def get_json(kind, digest):
    raw = get(kind, digest)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return None


def put_json(kind, digest, obj):
    put(kind, digest, json.dumps(obj, sort_keys=True).encode('utf-8'))
