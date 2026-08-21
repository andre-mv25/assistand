"""Utilidades de seguridad: cifrado y hashing.

- ``encrypt_text`` / ``encrypt_num``: cifran texto y numeros con Fernet
  (AES-128-CBC) usando la clave del servidor (``ENCRYPTION_KEY``). Los valores
  cifrados llevan el prefijo ``enc:`` para distinguirlos del texto plano.
- ``hash_key``: genera un hash SHA-256, usado para buscar por identificadores
  sin almacenar el valor original (username, token de sesion).
"""
import hashlib
from cryptography.fernet import Fernet, InvalidToken
from config import ENCRYPTION_KEY

ENC_PREFIX = "enc:"

_fernet = None


def _get_fernet():
    """Crea (una sola vez) la instancia de Fernet con la clave de cifrado."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(ENCRYPTION_KEY.encode())
    return _fernet


def encrypt_text(value) -> str | None:
    """Cifra un valor de texto con Fernet.

    Si el valor ya esta cifrado (empieza con ``enc:``) se devuelve tal cual.
    Devuelve ``None`` si el valor es ``None``.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        return value
    return ENC_PREFIX + _get_fernet().encrypt(str(value).encode()).decode()


def decrypt_text(value):
    """Descifra un valor cifrado con ``encrypt_text``.

    Si el valor no esta cifrado (sin prefijo ``enc:``) se devuelve tal cual.
    Si el descifrado falla (clave invalida o token corrupto) devuelve ``None``.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        try:
            return _get_fernet().decrypt(value[len(ENC_PREFIX):].encode()).decode()
        except InvalidToken:
            return None
    return value


def encrypt_num(value) -> str | None:
    """Cifra un valor numerico (convertido a texto) con Fernet."""
    if value is None:
        return None
    return ENC_PREFIX + _get_fernet().encrypt(str(value).encode()).decode()


def decrypt_num(value):
    """Descifra un numero cifrado con ``encrypt_num`` y lo devuelve como ``float``.

    Devuelve ``None`` si el valor no es descifrable o no es un numero valido.
    """
    if value is None:
        return None
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        try:
            return float(_get_fernet().decrypt(value[len(ENC_PREFIX):].encode()).decode())
        except (InvalidToken, ValueError):
            return None
    return value


def hash_key(value: str) -> str:
    """Devuelve el hash SHA-256 de un valor.

    Se usa para identificar usuarios y sesiones sin guardar el valor en texto
    plano (ej. ``username_hash``, ``token_hash``).
    """
    return hashlib.sha256(value.strip().encode()).hexdigest()
