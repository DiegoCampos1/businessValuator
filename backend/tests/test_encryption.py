import pytest

from app.core.encryption import EncryptionError, EncryptionService, key_hint


def test_roundtrip():
    svc = EncryptionService(EncryptionService.generate_key())
    token = svc.encrypt("sk-secret-123")
    assert token != "sk-secret-123"
    assert svc.decrypt(token) == "sk-secret-123"


def test_ciphertext_never_contains_plaintext():
    svc = EncryptionService(EncryptionService.generate_key())
    token = svc.encrypt("sk-abc123xyz")
    assert "sk-abc123xyz" not in token


def test_distinct_iv_produces_distinct_ciphertext():
    svc = EncryptionService(EncryptionService.generate_key())
    a = svc.encrypt("same-value")
    b = svc.encrypt("same-value")
    assert a != b


def test_key_hint_masks():
    assert key_hint("sk-abcdefghij") == "sk-...ghij"
    assert key_hint("short") == "sho***"


def test_invalid_master_key_raises():
    with pytest.raises(EncryptionError):
        EncryptionService("nao-eh-uma-fernet-key")


def test_decrypt_wrong_token_raises():
    svc = EncryptionService(EncryptionService.generate_key())
    with pytest.raises(EncryptionError):
        svc.decrypt("token-invalido")
