from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class TokenEncryptionError(RuntimeError):
    pass


def _fernet(key: str | None = None) -> Fernet:
    raw = (key if key is not None else get_settings().token_encryption_key).strip()
    if not raw:
        raise TokenEncryptionError(
            "TOKEN_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except (ValueError, TypeError) as exc:
        raise TokenEncryptionError("TOKEN_ENCRYPTION_KEY is not a valid Fernet key") from exc


def encrypt_token(plaintext: str, key: str | None = None) -> str:
    return _fernet(key).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str, key: str | None = None) -> str:
    try:
        return _fernet(key).decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise TokenEncryptionError("stored refresh token could not be decrypted") from exc
