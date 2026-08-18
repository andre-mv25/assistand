from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI_ATLAS, MONGO_URI_LOCAL, MONGO_DB

client: AsyncIOMotorClient = None
db = None
db_conectado = False
db_es_atlas = False


async def connect_db():
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
    global client, db, db_conectado, db_es_atlas
    if client:
        client.close()
        client = None
        db = None
        db_conectado = False
        db_es_atlas = False
        print("MongoDB desconectado")


def get_db():
    return db


def is_db_connected():
    return db_conectado


def is_db_atlas_connected():
    return db_es_atlas


async def insert_dual(collection_name: str, doc: dict):
    if db is None:
        return None
    return await db[collection_name].insert_one(doc)


async def delete_dual(collection_name: str, filtro: dict):
    if db is None:
        return None
    return await db[collection_name].delete_one(filtro)