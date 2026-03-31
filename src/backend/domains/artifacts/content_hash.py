"""Content hashing utility for artifact uploads."""

import hashlib

from fastapi import UploadFile


async def compute_hash(file: UploadFile) -> str:
    """Compute a SHA-256 hash of the uploaded file content.

    The file position is reset to 0 after hashing so the file can
    be read again by subsequent callers.
    """
    sha256 = hashlib.sha256()
    await file.seek(0)
    while chunk := await file.read(8192):
        sha256.update(chunk)
    await file.seek(0)
    return f"sha256:{sha256.hexdigest()}"
