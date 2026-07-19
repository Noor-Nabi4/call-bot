"""Metadata HMAC and credential encryption."""

from __future__ import annotations

from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner


def test_metadata_roundtrip(signer: MetadataSigner) -> None:
    raw = signer.sign_payload({"tenant_id": "abc", "did": "+15551234567"})
    parsed = signer.verify_and_parse(raw)
    assert parsed is not None
    assert parsed["tenant_id"] == "abc"
    assert parsed["did"] == "+15551234567"
    assert "sig" not in parsed


def test_metadata_rejects_tamper(signer: MetadataSigner) -> None:
    raw = signer.sign_payload({"tenant_id": "abc"})
    tampered = raw.replace("abc", "evil")
    assert signer.verify_and_parse(tampered) is None


def test_cipher_roundtrip(cipher: CredentialCipher) -> None:
    token = "twilio-auth-token-secret"
    enc = cipher.encrypt(token)
    assert enc != token
    assert cipher.decrypt(enc) == token
