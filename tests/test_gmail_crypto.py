from cryptography.fernet import Fernet

from app.gmail.crypto import decrypt_token, encrypt_token


def test_token_encryption_roundtrip() -> None:
    key = Fernet.generate_key().decode()
    secret = "refresh-token-value-not-for-logs"
    encrypted = encrypt_token(secret, key=key)
    assert secret not in encrypted
    assert decrypt_token(encrypted, key=key) == secret


def test_encrypted_token_is_not_plaintext() -> None:
    key = Fernet.generate_key().decode()
    encrypted = encrypt_token("ya29.secret", key=key)
    assert encrypted != "ya29.secret"
    assert not encrypted.startswith("ya29.")
