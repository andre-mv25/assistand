from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI_LOCAL, MONGO_DB

client: AsyncIOMotorClient = None
db = None
db_conectado = False


async def connect_db():
    global client, db, db_conectado

    try:
        client = AsyncIOMotorClient(MONGO_URI_LOCAL, serverSelectionTimeoutMS=5000)
        await client.admin.command("ping")
        db = client[MONGO_DB]
        db_conectado = True
        print(f"MongoDB Local conectado: {MONGO_DB}")
    except Exception as e:
        print(f"Error MongoDB Local: {e}")
        client = None
        db = None
        db_conectado = False


async def close_db():
    global client, db, db_conectado
    if client:
        client.close()
        client = None
    db = None
    db_conectado = False
    print("MongoDB desconectado")


def get_db():
    return db


def is_db_connected():
    return db_conectado