from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, MONGO_DB

client: AsyncIOMotorClient = None
db = None

async def connect_db():
    global client, db
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[MONGO_DB]
    try:
        await db.prices.create_index("moneda", unique=False)
        await db.analisis.create_index("timestamp", expireAfterSeconds=86400)
    except Exception as e:
        print(f"Error creating indexes: {e}")

async def close_db():
    global client
    if client:
        client.close()

def get_db():
    return db
