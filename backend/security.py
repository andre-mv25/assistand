import hashlib
from cryptography.fernet import Fernet, InvalidToken
from config import ENCRYPTION_KEY

ENC_PREFIX = "enc:"

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(ENCRYPTION_KEY.encode())
    return _fernet


def encrypt_text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        return value
    return ENC_PREFIX + _get_fernet().encrypt(str(value).encode()).decode()


def decrypt_text(value):
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        try:
            return _get_fernet().decrypt(value[len(ENC_PREFIX):].encode()).decode()
        except InvalidToken:
            return None
    return value


def encrypt_num(value) -> str | None:
    if value is None:
        return None
    return ENC_PREFIX + _get_fernet().encrypt(str(value).encode()).decode()


def decrypt_num(value):
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        try:
            return float(_get_fernet().decrypt(value[len(ENC_PREFIX):].encode()).decode())
        except (InvalidToken, ValueError):
            return None
    return value


def hash_key(value: str) -> str:
    return hashlib.sha256(value.strip().encode()).hexdigest()
