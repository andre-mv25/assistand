from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI_LOCAL, MONGO_URI_ATLAS, MONGO_DB

client: AsyncIOMotorClient = None
db = None
db_conectado = False

atlas_client: AsyncIOMotorClient = None
db_atlas = None
db_atlas_conectado = False


async def connect_db():
    global client, db, db_conectado, atlas_client, db_atlas, db_atlas_conectado
    client = atlas_client = None
    db = db_atlas = None
    db_conectado = db_atlas_conectado = False

    if MONGO_URI_LOCAL:
        try:
            client = AsyncIOMotorClient(MONGO_URI_LOCAL, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            db = client[MONGO_DB]
            db_conectado = True
            print(f"MongoDB local conectado: {MONGO_DB}")
        except Exception as e:
            print(f"Error conectando a MongoDB local: {e}")

    if MONGO_URI_ATLAS and MONGO_URI_ATLAS != MONGO_URI_LOCAL:
        try:
            atlas_client = AsyncIOMotorClient(MONGO_URI_ATLAS, serverSelectionTimeoutMS=5000)
            await atlas_client.admin.command("ping")
            db_atlas = atlas_client[MONGO_DB]
            db_atlas_conectado = True
            print(f"MongoDB Atlas conectado: {MONGO_DB}")
        except Exception as e:
            print(f"Error conectando a MongoDB Atlas: {e}")

    if not db_conectado and not db_atlas_conectado:
        print("MongoDB desactivado: ninguna base conectada")


async def close_db():
    global client, db, db_conectado, atlas_client, db_atlas, db_atlas_conectado
    for c in (client, atlas_client):
        if c:
            c.close()
    client = atlas_client = None
    db = db_atlas = None
    db_conectado = db_atlas_conectado = False
    print("MongoDB desconectado")


def get_db():
    return db if db is not None else db_atlas


def is_db_connected():
    return db_conectado


def is_db_atlas_connected():
    return db_atlas_conectado


def _bases_activas():
    bases = []
    if db is not None:
        bases.append(db)
    if db_atlas is not None and db_atlas is not db:
        bases.append(db_atlas)
    return bases


async def insert_dual(coleccion: str, documento: dict):
    bases = _bases_activas()
    if not bases:
        raise RuntimeError("No hay base de datos conectada")
    ultimo_error = None
    insertado_id = None
    for base in bases:
        try:
            res = await base[coleccion].insert_one(documento)
            if insertado_id is None:
                insertado_id = res.inserted_id
        except Exception as e:
            ultimo_error = e
            print(f"Error insertando en {coleccion}: {e}")
    if insertado_id is None:
        raise RuntimeError(f"No se pudo insertar en {coleccion}: {ultimo_error}")
    return insertado_id


async def delete_dual(coleccion: str, filtro: dict) -> int:
    bases = _bases_activas()
    if not bases:
        raise RuntimeError("No hay base de datos conectada")
    total = 0
    for base in bases:
        try:
            res = await base[coleccion].delete_one(filtro)
            total += res.deleted_count
        except Exception as e:
            print(f"Error eliminando de {coleccion}: {e}")
    return total