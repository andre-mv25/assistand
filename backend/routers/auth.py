"""Router de autenticación y gestión de sesiones de usuario.

Define los endpoints para registro de usuarios con validación de contraseña
fuerte, inicio de sesión mediante hash SHA-256 con salt aleatorio, consulta
del usuario autenticado y cierre de sesión.
"""
import re
import secrets
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import get_db, insert_dual, delete_dual
from security import hash_key, decrypt_text

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


class RegisterRequest(BaseModel):
    """Esquema de solicitud para registro de nuevo usuario."""
    username: str
    password: str


class LoginRequest(BaseModel):
    """Esquema de solicitud para inicio de sesión."""
    username: str
    password: str


def validar_password(p: str):
    """Valida la política de contraseñas: mínimo 8 caracteres, mayúscula, número y símbolo."""
    if len(p) < 8:
        return False, "La contrasena debe tener al menos 8 caracteres"
    if not re.search(r"[A-Z]", p):
        return False, "La contrasena debe incluir al menos una mayuscula"
    if not re.search(r"[0-9]", p):
        return False, "La contrasena debe incluir al menos un numero"
    if not re.search(r"[^A-Za-z0-9]", p):
        return False, "La contrasena debe incluir al menos un caracter especial (!, @, #, ...)"
    return True, ""


def hash_password(password: str) -> str:
    """Genera hash SHA-256 con salt aleatorio de 16 bytes."""
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    """Verifica si la contraseña coincide con el salt:hash almacenado."""
    try:
        salt, h = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except (ValueError, AttributeError):
        return False


def generar_token() -> str:
    """Genera un token de sesión seguro de 32 bytes (64 caracteres hex)."""
    return secrets.token_hex(32)


async def crear_sesion(username: str) -> str:
    """Crea una sesión para el usuario: genera un token y lo guarda (hash) en la BD.

    Args:
        username: nombre del usuario.
    Returns:
        El token de sesión (64 caracteres hex). La BD guarda solo su hash.
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
    """Valida un token de sesión contra la base de datos.

    Args:
        token: token de sesión a validar.
    Returns:
        El documento de la sesión (con ``username``) si es válido y no ha
        expirado; o ``None`` en caso contrario.
    """
    if not token:
        return None
    db = get_db()
    if db is None:
        return None
    try:
        from datetime import datetime as dt
        sesion = await db.sessions.find_one({
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
    """Registra un nuevo usuario (política de contraseña fuerte) y abre sesión.

    Args:
        req: ``{"username", "password"}`` (el usuario debe tener mínimo 3 chars
        y la contraseña mínimo 8 con mayúscula, número y símbolo).
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

    existing = await db.users.find_one({"username_hash": hash_key(req.username.strip())})
    if existing:
        return JSONResponse(content={"error": "El nombre de usuario ya existe"}, status_code=400)

    hashed = hash_password(req.password.strip())
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
    """Inicia sesión verificando credenciales y crea un token de sesión.

    Returns:
        ``{"success", "message", "token", "username"}``.
    """
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)

    user = await db.users.find_one({"username_hash": hash_key(req.username.strip())})
    if not user:
        return JSONResponse(content={"error": "El usuario no existe"}, status_code=404)

    if not verify_password(req.password.strip(), user["password"]):
        return JSONResponse(content={"error": "Contraseña incorrecta"}, status_code=401)

    token = await crear_sesion(req.username.strip())
    return {"success": True, "message": "Inicio de sesión exitoso", "token": token, "username": req.username.strip()}


@router.get("/me")
async def auth_me(token: str = Query("")):
    """Devuelve el usuario autenticado con el token, o 401 si es inválido."""
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    return {"success": True, "username": sesion["username"]}


@router.post("/logout")
async def logout(token: str = Query("")):
    """Cierra la sesión: elimina el documento de la sesión de la base de datos."""
    db = get_db()
    if db is not None and token:
        try:
            await delete_dual("sessions", {"token_hash": hash_key(token)})
        except Exception:
            pass
    return {"success": True}
