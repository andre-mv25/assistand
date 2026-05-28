import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "trading_assistant")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
FRANKFURTER_BASE_URL = "https://api.frankfurter.dev"
NEWS_API_BASE_URL = "https://newsapi.org/v2"
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

INTERVALO_ACTUALIZACION = int(os.getenv("INTERVALO_ACTUALIZACION", "60"))
