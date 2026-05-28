import httpx
from config import COINGECKO_BASE_URL

async def obtener_sentimiento_mercado():
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{COINGECKO_BASE_URL}/global")
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", {})
        if not data:
            return None
        market_cap_change = data.get("market_cap_change_percentage_24h_usd", 0)
        btc_dominance = data.get("market_cap_percentage", {}).get("btc", 0)
        total_volume = data.get("total_volume", {}).get("usd", 0)

        if market_cap_change > 2:
            sentimiento = "positivo"
            valor = round(0.3 + abs(market_cap_change) / 100, 2)
        elif market_cap_change < -2:
            sentimiento = "negativo"
            valor = round(-0.3 - abs(market_cap_change) / 100, 2)
        else:
            sentimiento = "neutral"
            valor = round(market_cap_change / 100, 2)

        return {
            "sentimiento": sentimiento,
            "valor": min(max(valor, -1), 1),
            "market_cap_change": round(market_cap_change, 2),
            "btc_dominance": round(btc_dominance, 1),
            "total_volume_usd": round(total_volume, 2),
        }


async def obtener_tendencias():
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{COINGECKO_BASE_URL}/search/trending")
        if resp.status_code != 200:
            return None
        data = resp.json().get("coins", [])
        if not data:
            return None
        return [
            {
                "nombre": c["item"]["name"],
                "simbolo": c["item"]["symbol"],
                "market_cap_rank": c["item"].get("market_cap_rank", 0),
                "precio_btc": c["item"].get("price_btc", 0),
            }
            for c in data[:5]
        ]
