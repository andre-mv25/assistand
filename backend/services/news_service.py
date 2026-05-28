import httpx
from config import NEWS_API_BASE_URL, NEWS_API_KEY

FUENTES_FINANCIERAS = {
    "bloomberg": "Bloomberg",
    "reuters": "Reuters",
    "cnbc": "CNBC",
    "bbc-news": "BBC News",
    "financial-times": "Financial Times",
    "the-wall-street-journal": "Wall Street Journal",
    "fortune": "Fortune",
    "business-insider": "Business Insider",
    "the-economist": "The Economist",
    "financial-post": "Financial Post",
}

async def obtener_noticias(
    query: str = "forex OR trading OR divisas",
    fuentes: list | None = None,
    cantidad: int = 10,
):
    if not NEWS_API_KEY:
        return None

    fuentes_str = ",".join(fuentes) if fuentes else ",".join(FUENTES_FINANCIERAS.keys())
    params = {
        "sources": fuentes_str,
        "q": query,
        "pageSize": min(cantidad, 100),
        "language": "en",
        "sortBy": "publishedAt",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{NEWS_API_BASE_URL}/everything",
            headers={"X-Api-Key": NEWS_API_KEY},
            params=params,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        articulos = data.get("articles", [])
        if not articulos:
            return None
        return [
            {
                "titulo": a.get("title", ""),
                "descripcion": a.get("description", ""),
                "fuente": a.get("source", {}).get("name", "Desconocida"),
                "url": a.get("url", ""),
                "imagen": a.get("urlToImage", ""),
                "fecha": a.get("publishedAt", ""),
                "autor": a.get("author", ""),
            }
            for a in articulos
        ]


async def obtener_portadas(categoria: str = "business", pais: str = "us", cantidad: int = 5):
    if not NEWS_API_KEY:
        return None

    params = {
        "category": categoria,
        "country": pais,
        "pageSize": min(cantidad, 100),
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{NEWS_API_BASE_URL}/top-headlines",
            headers={"X-Api-Key": NEWS_API_KEY},
            params=params,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        articulos = data.get("articles", [])
        if not articulos:
            return None
        return [
            {
                "titulo": a.get("title", ""),
                "descripcion": a.get("description", ""),
                "fuente": a.get("source", {}).get("name", "Desconocida"),
                "url": a.get("url", ""),
                "imagen": a.get("urlToImage", ""),
                "fecha": a.get("publishedAt", ""),
            }
            for a in articulos
        ]
