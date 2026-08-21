"""Servicio de noticias financieras via NewsAPI.

Consulta el endpoint ``/everything`` (noticias de fuentes financieras por tema)
y el endpoint ``/top-headlines`` (portadas por categoria/pais). Devuelve listas
de articulos normalizados con titulo, descripcion, fuente, URL, imagen y fecha.
"""
import httpx
from config import NEWS_API_BASE_URL, NEWS_API_KEY

# Fuentes financieras reconocidas por NewsAPI usadas por defecto
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
    """Busca noticias financieras en NewsAPI paginando hasta ``cantidad`` articulos.

    Args:
        query: terminos de busqueda.
        fuentes: lista de fuentes; si es ``None`` se usan ``FUENTES_FINANCIERAS``.
        cantidad: maximo de articulos a devolver.
    Returns:
        Lista de articulos normalizados o ``None`` si no hay clave o no hay resultados.
    """
    if not NEWS_API_KEY:
        return None

    fuentes_str = ",".join(fuentes) if fuentes else ",".join(FUENTES_FINANCIERAS.keys())
    articulos = []
    pagina = 1
    max_paginas = min((cantidad + 99) // 100, 20)

    async with httpx.AsyncClient(timeout=15) as client:
        while pagina <= max_paginas and len(articulos) < cantidad:
            params = {
                "sources": fuentes_str,
                "q": query,
                "pageSize": min(cantidad - len(articulos), 100),
                "language": "en",
                "sortBy": "publishedAt",
                "page": pagina,
            }
            try:
                resp = await client.get(
                    f"{NEWS_API_BASE_URL}/everything",
                    headers={"X-Api-Key": NEWS_API_KEY},
                    params=params,
                )
                if resp.status_code != 200:
                    break
                data = resp.json()
                nuevos = data.get("articles", [])
                if not nuevos:
                    break
                articulos += nuevos
                pagina += 1
            except Exception:
                break

    if not articulos:
        return None

    vistos = set()
    articulos_unicos = []
    for a in articulos:
        url = a.get("url", "")
        if url and url in vistos:
            continue
        if url:
            vistos.add(url)
        articulos_unicos.append(a)

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
        for a in articulos_unicos
    ]


async def obtener_portadas(categoria: str = "business", pais: str = "us", cantidad: int = 5):
    """Obtiene las portadas (top headlines) de NewsAPI por categoria y pais.

    Returns:
        Lista de articulos normalizados o ``None`` si falla o no hay resultados.
    """
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
