"""Router para gestión e historial de simulaciones de inversión por usuario.

Permite guardar, consultar y eliminar simulaciones realizadas por los usuarios,
aplicando cifrado selectivo con Fernet para proteger los datos sensibles
(montos, rendimientos, análisis IA y métricas).
"""
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import get_db, insert_dual, delete_dual
from security import encrypt_text, decrypt_text, encrypt_num, decrypt_num, hash_key
from routers.auth import validar_token

router = APIRouter(prefix="/api/simulaciones", tags=["Simulaciones"])

SIMULACION_CAMPOS_TEXTO = ["moneda", "sentimiento", "recomendacion", "analisis"]
SIMULACION_CAMPOS_NUMERO = [
    "monto", "capital_inicial", "capital_final", "rendimiento", "sharpe",
    "drawdown", "win_rate", "generado", "compound", "confianza",
]


class SimulacionRequest(BaseModel):
    """Esquema de solicitud para registrar una nueva simulación."""
    token: str
    moneda: str = ""
    monto: float = 0
    capital_inicial: float = 0
    capital_final: float = 0
    rendimiento: float = 0
    sharpe: float = 0
    drawdown: float = 0
    win_rate: float = 0
    generado: float = 0
    compound: float = 0
    sentimiento: str = ""
    recomendacion: str = ""
    confianza: float = 0
    analisis: str = ""


@router.post("")
@router.post("/")
async def guardar_simulacion(req: SimulacionRequest):
    """Guarda el resultado de una simulación vinculada al usuario autenticado.

    Cifra con Fernet los campos de texto y numéricos sensibles antes de
    insertarlos en la colección ``simulaciones``.
    Returns:
        ``{"success", "id"}`` del documento creado.
    """
    sesion = await validar_token(req.token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)
    try:
        doc = req.model_dump(exclude={"token"})
        doc["username_hash"] = hash_key(sesion["username"])
        doc["username"] = sesion["username"]
        doc["fecha"] = datetime.utcnow()
        for campo in SIMULACION_CAMPOS_TEXTO:
            v = doc.get(campo)
            if v is not None:
                doc[campo] = encrypt_text(v)
        for campo in SIMULACION_CAMPOS_NUMERO:
            v = doc.get(campo)
            if v is not None:
                doc[campo] = encrypt_num(v)
        res = await insert_dual("simulaciones", doc)
        return {"success": True, "id": str(res)}
    except Exception as e:
        print(f"Error guardando simulacion: {e}")
        return JSONResponse(content={"error": "No se pudo guardar la simulacion"}, status_code=500)


@router.get("")
@router.get("/")
async def listar_simulaciones(token: str = Query("")):
    """Lista el historial de simulaciones del usuario (descifrando los campos).

    Args:
        token: token de sesión del usuario.
    Returns:
        ``{"success", "simulaciones": [...]}`` (hasta 50, ordenadas por fecha).
    """
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)
    try:
        cursor = db.simulaciones.find({"username_hash": hash_key(sesion["username"])}).sort("fecha", -1).limit(50)
        simulaciones = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["username"] = doc.get("username") or decrypt_text(doc.get("username_enc"))
            for campo in SIMULACION_CAMPOS_TEXTO:
                doc[campo] = decrypt_text(doc.get(campo))
            for campo in SIMULACION_CAMPOS_NUMERO:
                doc[campo] = decrypt_num(doc.get(campo))
            simulaciones.append(doc)
        return {"success": True, "simulaciones": simulaciones}
    except Exception as e:
        print(f"Error listando simulaciones: {e}")
        return JSONResponse(content={"error": "No se pudo listar el historial"}, status_code=500)


@router.delete("/{sim_id}")
async def eliminar_simulacion(sim_id: str, token: str = Query("")):
    """Elimina una simulación del usuario (solo si le pertenece)."""
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)
    try:
        res = await delete_dual("simulaciones", {"_id": ObjectId(sim_id), "username_hash": hash_key(sesion["username"])})
        if res == 0:
            return JSONResponse(content={"error": "Simulacion no encontrada"}, status_code=404)
        return {"success": True}
    except Exception as e:
        print(f"Error eliminando simulacion: {e}")
        return JSONResponse(content={"error": "No se pudo eliminar la simulacion"}, status_code=500)
