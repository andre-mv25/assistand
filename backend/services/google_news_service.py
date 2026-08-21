"""Servicio de noticias via Google News RSS.

Consulta el feed RSS de Google News (``news.google.com/rss/search``) en espanol
de Mexico y normaliza los titulos/links/fuentes de los articulos obtenidos.
"""
import httpx
import re
import xml.etree.ElementTree as ET

GOOGLE_NEWS_URL = "https://news.google.com/rss/search"


def _limpiar_texto(texto: str) -> str:
    """Normaliza espacios y recorta un texto (para titulos/fuentes)."""
    return re.sub(r"\s+", " ", texto or "").strip()


async def obtener_noticias_google(
    query: str = "forex OR divisas OR tipo de cambio",
    cantidad: int = 100,
    idioma: str = "es-419",
    pais: str = "MX",
) -> list[dict] | None:
    """Obtiene noticias de Google News RSS y las normaliza.

    Args:
        query: terminos de busqueda.
        cantidad: maximo de articulos.
        idioma: idioma (es-419).
        pais: codigo de pais (MX).
    Returns:
        Lista de articulos normalizados o ``None`` si falla o no hay resultados.
    """
    params = {
        "q": query,
        "hl": idioma,
        "gl": pais,
        "ceid": f"{pais}:{idioma}",
        "num": min(cantidad, 100),
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(GOOGLE_NEWS_URL, params=params)
            if resp.status_code != 200:
                return None
            root = ET.fromstring(resp.text)
    except Exception:
        return None

    items = root.findall(".//item")
    if not items:
        return None

    resultado = []
    for item in items:
        titulo = _limpiar_texto(item.findtext("title", ""))
        if not titulo or len(titulo) < 15:
            continue
        link = item.findtext("link", "")
        fuente = _limpiar_texto(item.findtext("source", "Google News"))
        fecha_raw = item.findtext("pubDate", "")
        fecha = ""
        if fecha_raw:
            try:
                fecha = fecha_raw[:16]
            except (ValueError, IndexError):
                fecha = ""
        resultado.append({
            "titulo": titulo,
            "descripcion": "",
            "fuente": fuente,
            "url": link,
            "imagen": "",
            "fecha": fecha,
            "autor": "",
        })

    if not resultado:
        return None
    return resultado
