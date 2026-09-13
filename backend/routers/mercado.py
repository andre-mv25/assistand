"""Router de datos de mercado, cotizaciones Forex, noticias y sentimiento.

Define los endpoints para consultar precios en tiempo real (Yahoo Finance),
históricos de divisas, criptomonedas en tendencia (CoinGecko), noticias financieras
(NewsAPI), sentimiento léxico (VADER) y tipos de cambio oficiales (Banxico y DOF).
"""
from datetime import datetime
from fastapi import APIRouter, Query

from database import get_db, insert_dual
from services.yfinance_service import (
    obtener_precios_forex,
    obtener_historico_forex,
    obtener_precio_par,
    obtener_historico_par,
)
from services.coingecko_service import obtener_tendencias
from services.news_service import obtener_noticias, obtener_portadas
from services.vader_service import analizar_noticias as analizar_vader
from services.dof_service import obtener_tipo_cambio_dolar
from services.banxico_service import obtener_tipo_cambio, obtener_tipo_cambio_multiples

router = APIRouter(prefix="/api", tags=["Mercado"])


@router.get("/precios")
async def get_precios():
    """Obtiene las cotizaciones Forex actuales de todas las monedas soportadas."""
    monedas = await obtener_precios_forex()
    if monedas is None:
        return {"error": "No se pudieron obtener precios Forex"}, 503
    db = get_db()
    if db is not None:
        try:
            for moneda, data in monedas.items():
                await insert_dual("prices", {
                    "moneda": moneda,
                    "precio": data["precio"],
                    "cambio": data["cambio"],
                    "timestamp": datetime.utcnow(),
                })
        except Exception as e:
            print(f"Error DB insert: {e}")
    return {
        "monedas": monedas,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/precios/{moneda}")
async def get_precio_moneda(moneda: str):
    """Obtiene la cotización actual de una moneda concreta.

    Args:
        moneda: código (USD, MXN, JPY, EUR).
    """
    monedas = await obtener_precios_forex()
    if monedas is None:
        return {"error": "No se pudieron obtener precios Forex"}, 503
    data = monedas.get(moneda.upper())
    if not data:
        return {"error": f"Moneda {moneda} no soportada"}, 404
    return {
        "moneda": moneda.upper(),
        "precio": data["precio"],
        "cambio": data["cambio"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/par/{from_curr}/{to_curr}")
async def get_par(from_curr: str, to_curr: str):
    """Obtiene la tasa de cambio actual del par FROM/TO (ej. USD/MXN)."""
    par = await obtener_precio_par(from_curr.upper(), to_curr.upper())
    if par is None:
        return {"error": "No se pudo obtener el par"}, 503
    return par


@router.get("/historico_par/{from_curr}/{to_curr}")
async def get_historico_par(from_curr: str, to_curr: str, dias: int = Query(60)):
    """Obtiene el histórico diario del par FROM/TO.

    Args:
        dias: cantidad de días del histórico (default 60).
    Returns:
        ``{"from", "to", "datos": [...], "timestamp"}``.
    """
    historico = await obtener_historico_par(from_curr.upper(), to_curr.upper(), dias)
    if historico is None:
        return {"error": f"No se pudo obtener historico para {from_curr}/{to_curr}"}, 503
    return {
        "from": from_curr.upper(),
        "to": to_curr.upper(),
        "datos": historico,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/historico/{moneda}")
async def get_historico(moneda: str, dias: int = Query(30)):
    """Obtiene el histórico diario de una moneda frente al USD.

    Args:
        moneda: código de la divisa (JPY, EUR, MXN...).
        dias: cantidad de días del histórico (default 30).
    """
    historico = await obtener_historico_forex(moneda.upper(), dias)
    if historico is None:
        return {"error": f"No se pudo obtener historico para {moneda.upper()}"}, 503
    return {
        "moneda": moneda.upper(),
        "datos": historico,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/tendencias")
async def get_tendencias():
    """Obtiene las criptomonedas más buscadas (trending) en CoinGecko."""
    tendencias = await obtener_tendencias()
    if tendencias is None:
        return {"error": "No se pudieron obtener tendencias"}, 503
    return {
        "tendencias": tendencias,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/noticias")
async def get_noticias(
    query: str = Query("forex OR trading OR divisas"),
    fuentes: str = Query(None),
    cantidad: int = Query(10, ge=1, le=50),
):
    """Busca noticias financieras en NewsAPI.

    Args:
        query: términos de búsqueda.
        fuentes: lista de fuentes separadas por coma (opcional).
        cantidad: número de artículos (1-50).
    """
    lista_fuentes = fuentes.split(",") if fuentes else None
    noticias = await obtener_noticias(query, lista_fuentes, cantidad)
    if noticias is None:
        return {"error": "No se pudieron obtener noticias"}, 503
    return {
        "noticias": noticias,
        "total": len(noticias),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/noticias/portadas")
async def get_portadas(
    categoria: str = Query("business"),
    pais: str = Query("us"),
    cantidad: int = Query(5, ge=1, le=20),
):
    """Obtiene las portadas de noticias por categoría y país (NewsAPI)."""
    noticias = await obtener_portadas(categoria, pais, cantidad)
    if noticias is None:
        return {"error": "No se pudieron obtener portadas"}, 503
    return {
        "noticias": noticias,
        "total": len(noticias),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/vader")
async def get_vader(query: str = Query("forex OR trading OR divisas"), cantidad: int = Query(2000, ge=1, le=2000)):
    """Analiza el sentimiento del mercado con VADER sobre las noticias obtenidas.

    Args:
        query: términos de búsqueda.
        cantidad: máximo de artículos a analizar (hasta 2000).
    """
    resultado = await analizar_vader(query=query, cantidad=cantidad)
    if resultado is None:
        return {"error": "No se pudieron analizar noticias con VADER"}, 503
    return resultado


@router.get("/dof/tipo_cambio")
async def get_dof_tipo_cambio():
    """Obtiene el tipo de cambio del dólar publicado en el DOF (Diario Oficial)."""
    resultado = await obtener_tipo_cambio_dolar()
    if resultado is None:
        return {"error": "No se pudo obtener el tipo de cambio del DOF"}, 503
    return resultado


@router.get("/banxico/tipo_cambio")
async def get_banxico_tipo_cambio(moneda: str = Query("USD")):
    """Obtiene el tipo de cambio oficial FIX de Banxico para una moneda."""
    resultado = await obtener_tipo_cambio(moneda)
    if resultado is None:
        return {"error": f"No se pudo obtener el tipo de cambio de {moneda} en Banxico"}, 503
    return resultado


@router.get("/banxico/tipo_cambio_all")
async def get_banxico_tipo_cambio_all():
    """Obtiene los tipos de cambio FIX de Banxico para todas las monedas soportadas."""
    resultado = await obtener_tipo_cambio_multiples()
    if resultado is None:
        return {"error": "No se pudieron obtener los tipos de cambio de Banxico"}, 503
    return resultado
