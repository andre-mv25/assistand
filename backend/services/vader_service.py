"""Analisis de sentimiento de noticias con VADER.

Reune articulos de NewsAPI, Google News y GNews, los analiza con
``vaderSentiment`` y produce un puntaje compuesto (de -1 a +1) con su
clasificacion (alta / baja / neutral). Es la primera capa del semaforo.
"""
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from .news_service import obtener_noticias
from .google_news_service import obtener_noticias_google
from .gnews_service import obtener_noticias_gnews

_analizador = SentimentIntensityAnalyzer()

POSITIVO = 0.05
NEGATIVO = -0.05


def clasificar(compound: float) -> str:
    """Clasifica un puntaje compuesto: alta (>= 0.05), baja (<= -0.05) o neutral."""
    if compound >= POSITIVO:
        return "alta"
    if compound <= NEGATIVO:
        return "baja"
    return "neutral"


async def analizar_noticias(query: str = "forex OR trading OR divisas", cantidad: int = 100) -> dict | None:
    """Analiza el sentimiento del mercado a partir de noticias de varias fuentes.

    Args:
        query: terminos de busqueda para NewsAPI.
        cantidad: maximo de articulos solicitados a NewsAPI.
    Returns:
        Diccionario con ``compound_score``, ``clasificacion``, conteos por fuente,
        y las noticias analizadas; o ``None`` si no hay articulos disponibles.
    """
    newsapi = await obtener_noticias(query=query, cantidad=cantidad)
    google = await obtener_noticias_google(query="forex OR divisas OR tipo de cambio", cantidad=100)
    gnews = await obtener_noticias_gnews(query="forex OR divisas OR tipo de cambio", cantidad=10)

    articulos = []
    vistos = set()
    for grupo in (newsapi, google, gnews):
        if not grupo:
            continue
        for a in grupo:
            url = a.get("url", "")
            if url and url in vistos:
                continue
            if url:
                vistos.add(url)
            articulos.append(a)

    compuestos = []

    total_newsapi = len(newsapi) if newsapi else 0
    total_google = len(google) if google else 0
    total_gnews = len(gnews) if gnews else 0

    # Análisis de sentimiento con VADER
    if articulos:
        for a in articulos:
            texto = f"{a['titulo']}. {a['descripcion']}" if a['descripcion'] else a['titulo']
            if not texto.strip():
                continue
            scores = _analizador.polarity_scores(texto)
            compuestos.append(scores["compound"])

    if not compuestos:
        return None

    compound_final = sum(compuestos) / len(compuestos)
    compound_final = max(-1.0, min(1.0, compound_final))

    noticias_combinadas = [
        {"titulo": a["titulo"], "fuente": a["fuente"], "fecha": a["fecha"], "url": a.get("url", "")}
        for a in articulos[:10]
    ]

    return {
        "compound_score": round(compound_final, 4),
        "clasificacion": clasificar(compound_final),
        "umbral_positivo": POSITIVO,
        "umbral_negativo": NEGATIVO,
        "noticias_analizadas": len(compuestos),
        "total_newsapi": total_newsapi,
        "total_google": total_google,
        "total_gnews": total_gnews,
        "source": "VADER (NewsAPI + Google News + GNews)",
        "noticias": noticias_combinadas,
    }


def analizar_texto(texto: str) -> dict:
    """Analiza el sentimiento de un texto suelto con VADER.

    Returns:
        ``{"compound_score", "clasificacion", "detalle"}``.
    """
    scores = _analizador.polarity_scores(texto)
    compound = scores["compound"]
    return {
        "compound_score": round(compound, 4),
        "clasificacion": clasificar(compound),
        "detalle": scores,
    }
