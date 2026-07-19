"""Credential encryption helpers."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipher:
    """Encrypt/decrypt provider secrets with a Fernet key derived from settings."""

    def __init__(self, key_material: str) -> None:
        if not key_material or not key_material.strip():
            raise ValueError("CREDENTIALS_ENCRYPTION_KEY is required")
        # Accept raw Fernet key or arbitrary secret (hashed to 32 bytes).
        raw = key_material.strip().encode("utf-8")
        try:
            self._fernet = Fernet(raw)
        except (ValueError, InvalidToken, Exception):
            digest = hashlib.sha256(raw).digest()
            self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
