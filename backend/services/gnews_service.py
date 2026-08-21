"""Servicio de noticias via GNews API.

Consulta el endpoint de busqueda de GNews (espanol / Mexico) con cache interna
de 15 minutos para no repetir llamadas a la API y normaliza los articulos.
"""
import httpx
import re
import time
from config import GNEWS_API_KEY

GNEWS_BASE_URL = "https://gnews.io/api/v4"
CACHE_TTL_SEGUNDOS = 900  # 15 minutos
_cache = {"timestamp": 0.0, "data": None}


def _limpiar_texto(texto: str) -> str:
    """Normaliza espacios y recorta un texto."""
    return re.sub(r"\s+", " ", texto or "").strip()


async def obtener_noticias_gnews(
    query: str = "forex OR divisas OR tipo de cambio",
    cantidad: int = 10,
    idioma: str = "es",
    pais: str = "mx",
) -> list[dict] | None:
    """Obtiene noticias de GNews (con cache de 15 min) y las normaliza.

    Args:
        query: terminos de busqueda.
        cantidad: maximo de articulos.
        idioma: idioma (es).
        pais: codigo de pais (mx).
    Returns:
        Lista de articulos normalizados o ``None`` si falla.
    """
    if not GNEWS_API_KEY:
        return None

    ahora = time.time()
    if _cache["data"] is not None and (ahora - _cache["timestamp"]) < CACHE_TTL_SEGUNDOS:
        return _cache["data"]

    params = {
        "q": query,
        "apikey": GNEWS_API_KEY,
        "max": min(cantidad, 100),
        "lang": idioma,
        "country": pais,
        "sortby": "publishedAt",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(f"{GNEWS_BASE_URL}/search", params=params)
            if resp.status_code != 200:
                return _cache["data"]
            data = resp.json()
    except Exception:
        return _cache["data"]

    articulos = data.get("articles", [])
    if not articulos:
        return _cache["data"]

    resultado = []
    for a in articulos:
        titulo = _limpiar_texto(a.get("title", ""))
        if not titulo or len(titulo) < 15:
            continue
        resultado.append({
            "titulo": titulo,
            "descripcion": _limpiar_texto(a.get("description", "")),
            "fuente": _limpiar_texto(a.get("source", {}).get("name", "GNews")),
            "url": a.get("url", ""),
            "imagen": a.get("image", ""),
            "fecha": a.get("publishedAt", ""),
            "autor": "",
        })

    if not resultado:
        return _cache["data"]

    _cache["timestamp"] = ahora
    _cache["data"] = resultado
    return resultado
