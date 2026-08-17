from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, MONGO_DB

client: AsyncIOMotorClient = None
db = None
db_conectado = False


async def connect_db():
    global client, db, db_conectado
    if not MONGO_URI:
        print("MONGO_URI no configurada, DB desactivada")
        return
    try:
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        await client.admin.command("ping")
        db = client[MONGO_DB]
        db_conectado = True
        print(f"MongoDB conectado: {MONGO_DB}")
    except Exception as e:
        print(f"Error conectando a MongoDB: {e}")
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