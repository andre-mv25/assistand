import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI_LOCAL = os.getenv("MONGO_URI_LOCAL", "mongodb://localhost:27017")
MONGO_URI_ATLAS = os.getenv("MONGO_URI_ATLAS", "")
MONGO_DB = os.getenv("MONGO_DB", "trading_assistant")

MONGO_URI = MONGO_URI_ATLAS or MONGO_URI_LOCAL

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
FRANKFURTER_BASE_URL = "https://api.frankfurter.dev"
NEWS_API_BASE_URL = "https://newsapi.org/v2"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

BANXICO_API_KEY = os.getenv("BANXICO_API_KEY", "")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")

ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

INTERVALO_ACTUALIZACION = int(os.getenv("INTERVALO_ACTUALIZACION", "60"))
