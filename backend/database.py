"""Capa de acceso a MongoDB (Motor / async).

Gestiona la conexion a la base de datos con respaldo automatico: intenta
conectarse primero a MongoDB Atlas (nube) y, si falla, cae a MongoDB local.
Tambien expone operaciones genericas de lectura/escritura para las colecciones.
"""
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI_ATLAS, MONGO_URI_LOCAL, MONGO_DB

# Estado global de la conexion
client: AsyncIOMotorClient = None
db = None
db_conectado = False
db_es_atlas = False


async def connect_db():
    """Establece la conexion a MongoDB.

    Prueba cada URI de ``config`` (Atlas primero, luego local) hasta conseguir
    una conexion valida. Actualiza los indicadores globales ``db_conectado`` y
    ``db_es_atlas`` segun el resultado.
    """
    global client, db, db_conectado, db_es_atlas
    uris = [MONGO_URI_ATLAS, MONGO_URI_LOCAL]
    uris = list(dict.fromkeys(uri for uri in uris if uri))
    for uri in uris:
        try:
            c = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
            await c.admin.command("ping")
            client = c
            db = client[MONGO_DB]
            db_conectado = True
            db_es_atlas = uri.startswith("mongodb+srv://")
            origen = "Atlas" if db_es_atlas else "local"
            print(f"MongoDB conectado ({origen}): {MONGO_DB}")
            return
        except Exception as e:
            print(f"Error conectando a MongoDB ({uri[:30]}...): {e}")
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


def get_db():
    """Devuelve el objeto de base de datos activo (o ``None`` si no hay conexion)."""
    return db


def is_db_connected():
    """Indica si hay una conexion activa a MongoDB (Atlas o local)."""
    return db_conectado


def is_db_atlas_connected():
    """Indica si la conexion activa es contra MongoDB Atlas (nube)."""
    return db_es_atlas


async def insert_dual(collection_name: str, doc: dict):
    """Inserta un documento en la coleccion indicada.

    Args:
        collection_name: nombre de la coleccion (users, sessions, simulaciones...).
        doc: documento a insertar.
    Returns:
        Resultado de ``insert_one`` de PyMongo o ``None`` si no hay base de datos.
    """
    if db is None:
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
    if db is None:
        return None
    return await db[collection_name].delete_one(filtro)