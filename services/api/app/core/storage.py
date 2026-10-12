"""Content-addressed file store (rule R16): files/<first 2 hex>/<sha256>, hashed while streaming to disk.
The same bytes are stored once; an original is never overwritten."""

import hashlib
import os
import tempfile
from pathlib import Path

from app.settings import get_settings

CHUNK = 64 * 1024


class TooLarge(Exception):
    pass


def path_for(sha256: str) -> Path:
    return get_settings().files_dir / sha256[:2] / sha256


def uri_for(sha256: str) -> str:
    return f"files/{sha256[:2]}/{sha256}"


def store_stream(chunks, max_bytes: int) -> tuple[str, int]:
    """Write chunks to a temp file while hashing; move into place by hash. Returns (sha256, size)."""
    root = get_settings().files_dir
    root.mkdir(parents=True, exist_ok=True)
    h, size = hashlib.sha256(), 0
    fd, tmp = tempfile.mkstemp(dir=root, prefix=".upload-")
    try:
        with os.fdopen(fd, "wb") as f:
            for chunk in chunks:
                size += len(chunk)
                if size > max_bytes:
                    raise TooLarge(f"larger than {max_bytes} bytes")
                h.update(chunk)
                f.write(chunk)
        sha = h.hexdigest()
        dest = path_for(sha)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            os.unlink(tmp)          # same bytes already stored: keep the original untouched
        else:
            os.replace(tmp, dest)
            os.chmod(dest, 0o444)
        return sha, size
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def store_bytes(data: bytes, max_bytes: int) -> tuple[str, int]:
    return store_stream((data[i:i + CHUNK] for i in range(0, len(data), CHUNK)), max_bytes)


def rehash(sha256: str) -> bool:
    """Does the stored file still hash to its name? (evidence check)"""
    p = path_for(sha256)
    if not p.exists():
        return False
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest() == sha256
