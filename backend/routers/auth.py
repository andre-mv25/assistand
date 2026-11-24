"""Router de autenticacion y gestion de sesiones de usuario.

Define los endpoints para registro de usuarios con validacion de contrasena
fuerte, inicio de sesion mediante hash PBKDF2-HMAC-SHA256 con salt aleatorio,
consulta del usuario autenticado y cierre de sesion.
"""
import re
import asyncio
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import get_db, insert_dual, delete_dual, find_one, update_one
from security import hash_key, decrypt_text

router = APIRouter(prefix="/api/auth", tags=["Autenticacion"])


class RegisterRequest(BaseModel):
    """Esquema de solicitud para registro de nuevo usuario."""
    username: str
    password: str


class LoginRequest(BaseModel):
    """Esquema de solicitud para inicio de sesion."""
    username: str
    password: str


def validar_password(p: str):
    """Valida la politica de contrasenas: minimo 8 caracteres, mayuscula, numero y simbolo."""
    if len(p) < 8:
        return False, "La contrasena debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", p):
        return False, "La contrasena debe incluir al menos una mayuscula"
    if not re.search(r"[0-9]", p):
        return False, "La contrasena debe incluir al menos un numero"
    if not re.search(r"[^A-Za-z0-9]", p):
        return False, "La contrasena debe incluir al menos un caracter especial (!, @, #, ...)"
    return True, ""


PBKDF2_ALGORITMO = "pbkdf2_sha256"
PBKDF2_ITERACIONES = 600_000  # Recomendacion OWASP 2023 para PBKDF2-HMAC-SHA256


def hash_password(password: str) -> str:
    """Genera el hash de la contrasena con PBKDF2-HMAC-SHA256 y salt aleatorio.

    PBKDF2 aplica la funcion hash cientos de miles de veces, lo que hace muy
    costoso un ataque de fuerza bruta aunque se filtre la base de datos.
    Formato almacenado: ``pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>``.
    """
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERACIONES).hex()
    return f"{PBKDF2_ALGORITMO}${PBKDF2_ITERACIONES}${salt}${h}"


def es_hash_legado(stored: str) -> bool:
    """Indica si el hash es del formato anterior (``salt:sha256``) y debe actualizarse."""
    return isinstance(stored, str) and not stored.startswith(PBKDF2_ALGORITMO + "$")


def verify_password(password: str, stored: str) -> bool:
    """Verifica la contrasena contra el hash almacenado (comparacion en tiempo constante).

    Acepta el formato actual (PBKDF2) y el formato legado ``salt:sha256`` para
    que las cuentas creadas antes del cambio sigan funcionando; esas cuentas se
    migran a PBKDF2 automaticamente en su siguiente inicio de sesion.
    """
    try:
        if stored.startswith(PBKDF2_ALGORITMO + "$"):
            _, iteraciones, salt, h = stored.split("$")
            calculado = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iteraciones)).hex()
        else:
            salt, h = stored.split(":")
            calculado = hashlib.sha256((salt + password).encode()).hexdigest()
        return hmac.compare_digest(calculado, h)
    except (ValueError, AttributeError):
        return False


def generar_token() -> str:
    """Genera un token de sesion seguro de 32 bytes (64 caracteres hex)."""
    return secrets.token_hex(32)


async def crear_sesion(username: str) -> str:
    """Crea una sesion para el usuario: genera un token y lo guarda (hash) en la BD.

    Args:
        username: nombre del usuario.
    Returns:
        El token de sesion (64 caracteres hex). La BD guarda solo su hash.
    """
    token = generar_token()
    db = get_db()
    if db is not None:
        try:
            await insert_dual("sessions", {
                "token_hash": hash_key(token),
                "username_hash": hash_key(username),
                "username": username,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=30),
            })
        except Exception as e:
            print(f"Error creando sesion: {e}")
    return token


async def validar_token(token: str):
    """Valida un token de sesion contra la base de datos.

    Args:
        token: token de sesion a validar.
    Returns:
        El documento de la sesion (con ``username``) si es valido y no ha
        expirado; o ``None`` en caso contrario.
    """
    if not token:
        return None
    db = get_db()
    if db is None:
        return None
    try:
        from datetime import datetime as dt
        sesion = await find_one("sessions", {
            "token_hash": hash_key(token),
            "expires_at": {"$gt": dt.utcnow()},
        })
        if sesion:
            sesion["username"] = sesion.get("username") or decrypt_text(sesion.get("username_enc"))
        return sesion
    except Exception:
        return None


@router.post("/register")
async def register(req: RegisterRequest):
    """Registra un nuevo usuario (politica de contrasena fuerte) y abre sesion.

    Args:
        req: ``{"username", "password"}`` (el usuario debe tener minimo 3 chars
        y la contrasena minimo 8 con mayuscula, numero y simbolo).
    Returns:
        ``{"success", "message", "token", "username"}``.
    """
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)

    if len(req.username.strip()) < 3:
        return JSONResponse(content={"error": "El usuario debe tener al menos 3 caracteres"}, status_code=400)
    valida_ok, valida_msg = validar_password(req.password.strip())
    if not valida_ok:
        return JSONResponse(content={"error": valida_msg}, status_code=400)

    existing = await find_one("users", {"username_hash": hash_key(req.username.strip())})
    if existing:
        return JSONResponse(content={"error": "El nombre de usuario ya existe"}, status_code=400)

    hashed = await asyncio.to_thread(hash_password, req.password.strip())
    await insert_dual("users", {
        "username_hash": hash_key(req.username.strip()),
        "username": req.username.strip(),
        "password": hashed,
        "created_at": datetime.utcnow(),
    })
    token = await crear_sesion(req.username.strip())
    return {"success": True, "message": "Cuenta creada exitosamente", "token": token, "username": req.username.strip()}


@router.post("/login")
async def login(req: LoginRequest):
    """Inicia sesion verificando credenciales y crea un token de sesion.

    Returns:
        ``{"success", "message", "token", "username"}``.
    """
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)

    user = await find_one("users", {"username_hash": hash_key(req.username.strip())})
    if not user:
        return JSONResponse(content={"error": "El usuario no existe"}, status_code=404)

    if not await asyncio.to_thread(verify_password, req.password.strip(), user["password"]):
        return JSONResponse(content={"error": "Contrasena incorrecta"}, status_code=401)

    # Migracion transparente: si la cuenta usa el hash anterior (SHA-256 simple),
    # se reemplaza por PBKDF2 ahora que se conoce la contrasena correcta.
    if es_hash_legado(user["password"]):
        try:
            await update_one(
                "users",
                {"_id": user["_id"]},
                {"$set": {"password": await asyncio.to_thread(hash_password, req.password.strip())}},
            )
        except Exception as e:
            print(f"Error migrando hash de contrasena: {e}")

    token = await crear_sesion(req.username.strip())
    return {"success": True, "message": "Inicio de sesion exitoso", "token": token, "username": req.username.strip()}


@router.get("/me")
async def auth_me(token: str = Query("")):
    """Devuelve el usuario autenticado con el token, o 401 si es invalido."""
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesion invalida o expirada"}, status_code=401)
    return {"success": True, "username": sesion["username"]}


@router.post("/logout")
async def logout(token: str = Query("")):
    """Cierra la sesion: elimina el documento de la sesion de la base de datos."""
    db = get_db()
    if db is not None and token:
        try:
            await delete_dual("sessions", {"token_hash": hash_key(token)})
        except Exception:
            pass
    return {"success": True}
