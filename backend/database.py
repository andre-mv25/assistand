"""Capa de acceso a MongoDB (Motor / async).

Gestiona la conexion a la base de datos con respaldo automatico: intenta
conectarse primero a MongoDB Atlas (nube) y, si falla, cae a MongoDB local.
Tambien expone operaciones genericas de lectura/escritura para las colecciones.
Incluye reintentos con backoff exponencial para mayor robustez ante fallas
transitorias de red o de Atlas.
"""
import certifi
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI_ATLAS, MONGO_URI_LOCAL, MONGO_DB

# Estado global de la conexion
client: AsyncIOMotorClient = None
db = None
db_conectado = False
db_es_atlas = False


async def _probar_conexion(uri: str, timeout_ms: int = 8000) -> bool:
    """Intenta hacer ping a la URI indicada. Devuelve True si responde."""
    try:
        kwargs = {"serverSelectionTimeoutMS": timeout_ms}
        if uri.startswith("mongodb+srv://"):
            kwargs["tlsCAFile"] = certifi.where()
        c = AsyncIOMotorClient(uri, **kwargs)
        await c.admin.command("ping")
        c.close()
        return True
    except Exception:
        return False


async def connect_db():
    """Establece la conexion a MongoDB.

    Prueba cada URI de ``config`` (Atlas primero, luego local) hasta conseguir
    una conexion valida. Incluye reintentos con backoff exponencial por cada URI.
    Actualiza los indicadores globales ``db_conectado`` y ``db_es_atlas``.
    """
    global client, db, db_conectado, db_es_atlas

    uris = [MONGO_URI_ATLAS, MONGO_URI_LOCAL]
    uris = list(dict.fromkeys(uri for uri in uris if uri))

    for uri in uris:
        origen = "Atlas" if uri.startswith("mongodb+srv://") else "local"
        ultimo_error = None

        # Hasta 3 reintentos con backoff exponencial (1s, 2s, 4s)
        for intento in range(1, 4):
            try:
                kwargs = {"serverSelectionTimeoutMS": 8000}
                if uri.startswith("mongodb+srv://"):
                    kwargs["tlsCAFile"] = certifi.where()
                c = AsyncIOMotorClient(uri, **kwargs)
                await c.admin.command("ping")

                client = c
                db = client[MONGO_DB]
                db_conectado = True
                db_es_atlas = uri.startswith("mongodb+srv://")
                print(f"MongoDB conectado ({origen}): {MONGO_DB}")
                return
            except Exception as e:
                ultimo_error = e
                if intento < 3:
                    espera = 2 ** (intento - 1)
                    print(f"Error conectando a {origen} (intento {intento}/3): {e}. Reintentando en {espera}s...")
                    await asyncio.sleep(espera)

        print(f"Error conectando a MongoDB ({origen}): {ultimo_error}")

    db_conectado = False
    db_es_atlas = False


async def close_db():
    """Cierra la conexion activa a MongoDB y limpia el estado global."""
    global client, db, db_conectado, db_es_atlas
    if client:
        client.close()
        client = None
        db = None
        db_conectado = False
        db_es_atlas = False
        print("MongoDB desconectado")


async def reconnect_db() -> bool:
    """Intenta reconectar si la BD esta desconectada. Devuelve True si logra conectar."""
    if db_conectado:
        return True
    await connect_db()
    return db_conectado


def get_db():
    """Devuelve el objeto de base de datos activo (o ``None`` si no hay conexion)."""
    return db


def is_db_connected():
    """Indica si hay una conexion activa a MongoDB (Atlas o local)."""
    return db_conectado


def is_db_atlas_connected():
    """Indica si la conexion activa es contra MongoDB Atlas (nube)."""
    return db_es_atlas


async def _ensure_db():
    """Garantiza que haya una conexion activa antes de operar. Intenta reconectar si hace falta."""
    global db_conectado
    if not db_conectado:
        await connect_db()
    return db_conectado


async def insert_dual(collection_name: str, doc: dict):
    """Inserta un documento en la coleccion indicada.

    Args:
        collection_name: nombre de la coleccion (users, sessions, simulaciones...).
        doc: documento a insertar.
    Returns:
        Resultado de ``insert_one`` de PyMongo o ``None`` si no hay base de datos.
    """
    if not await _ensure_db() or db is None:
        return None
    return await db[collection_name].insert_one(doc)


async def delete_dual(collection_name: str, filtro: dict):
    """Elimina un documento que cumpla el filtro en la coleccion indicada.

    Args:
        collection_name: nombre de la coleccion.
        filtro: criterio de busqueda (ej. {"_id": ObjectId(...)}).
    Returns:
        Resultado de ``delete_one`` o ``None`` si no hay base de datos.
    """
    if not await _ensure_db() or db is None:
        return None
    return await db[collection_name].delete_one(filtro)


async def find_one(collection_name: str, filtro: dict):
    """Busca un documento en la coleccion indicada."""
    if not await _ensure_db() or db is None:
        return None
    return await db[collection_name].find_one(filtro)


async def find_many(collection_name: str, filtro: dict, sort: list = None, limit: int = 50):
    """Busca varios documentos en la coleccion indicada."""
    if not await _ensure_db() or db is None:
        return []
    cursor = db[collection_name].find(filtro)
    if sort:
        cursor = cursor.sort(sort)
    cursor = cursor.limit(limit)
    resultados = []
    async for doc in cursor:
        resultados.append(doc)
    return resultados


async def update_one(collection_name: str, filtro: dict, actualizacion: dict):
    """Actualiza un documento que cumpla el filtro."""
    if not await _ensure_db() or db is None:
        return None
    return await db[collection_name].update_one(filtro, actualizacion)
