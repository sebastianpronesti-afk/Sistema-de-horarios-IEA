"""Read a catalog supplied as private deployment variables, without filesystem writes."""
import base64
from functools import lru_cache
import gzip
import hashlib
import io
import json
import os
import re
import zlib

PREFIX = 'CURRICULUM_CATALOG_GZIP_'
MAX_BYTES = 16 * 1024 * 1024


@lru_cache(maxsize=2)
def _decode(parts, expected_hash):
    try:
        compressed = base64.b64decode(''.join(parts), validate=True)
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError('El catálogo supera el tamaño admitido')
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError('El catálogo privado no coincide con su hash')
        data=json.loads(raw)
        if not isinstance(data,dict):
            raise ValueError('El catálogo privado debe ser un objeto')
        return data
    except (ValueError, OSError, EOFError, zlib.error) as exc:
        raise ValueError('El catálogo privado está incompleto o es inválido') from exc


def read_bundle():
    count = os.environ.get(PREFIX + 'PARTS')
    if count is None and not any(key.startswith(PREFIX) for key in os.environ):
        return None
    if not count or not re.fullmatch(r'[1-9][0-9]?', count) or int(count) > 64:
        raise ValueError('Cantidad de partes del catálogo privado inválida')
    expected_hash = os.environ.get(PREFIX + 'SHA256', '')
    if not re.fullmatch(r'[a-f0-9]{64}', expected_hash):
        raise ValueError('Hash del catálogo privado ausente o inválido')
    parts = tuple(os.environ.get(f'{PREFIX}PART_{i:02d}', '') for i in range(1, int(count) + 1))
    if any(not part or len(part) > 48000 for part in parts):
        raise ValueError('Faltan partes del catálogo privado o exceden el tamaño admitido')
    return _decode(parts, expected_hash)
