"""Router para análisis de sentimiento IA (DeepSeek) y pronósticos estadísticos (ARIMA/ARMA).

Define los endpoints para el pronóstico a 5 días con bandas de confianza,
el análisis en tiempo real por divisa (combinando DeepSeek y noticias) y
el veredicto final sobre la simulación completa del usuario.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Query, Body

from database import get_db, insert_dual
from security import encrypt_text
from services.arima_service import pronostico_arima, senal_arma_desde_precios
from services.yfinance_service import obtener_precios_forex, obtener_historico_par
from services.deepseek_service import analizar_sentimiento, analizar_semaforo, analizar_historico
from services.news_service import obtener_noticias
from services.acciones_service import obtener_acciones

router = APIRouter(prefix="/api", tags=["Análisis"])


def _fallback_vader(moneda: str, rendimiento: float, sharpe: float, vader: dict | None):
    """Análisis degradado basado en VADER cuando DeepSeek no está disponible."""
    if not vader:
        return None
    compound = vader.get("compound_score", 0.0) or 0.0
    clasif = vader.get("clasificacion", "neutral") or "neutral"

    if clasif == "alta":
        sentimiento, recomendacion = "alta", "COMPRAR"
    elif clasif == "baja":
        sentimiento, recomendacion = "baja", "VENDER"
    else:
        sentimiento, recomendacion = "neutral", "MANTENER"

    return {
        "sentimiento": sentimiento,
        "valor": round(max(-1.0, min(1.0, compound)), 2),
        "analisis": f"DeepSeek no disponible; analisis en modo degradado con VADER ({vader.get('noticias_analizadas', 0)} noticias, clasificacion {clasif.upper()}). Rendimiento de la simulacion: {rendimiento:.2f}%, Sharpe: {sharpe:.2f}.",
        "recomendacion": recomendacion,
        "confianza": round(min(0.5, abs(compound) + 0.15), 2),
        "patron_encontrado": "Analisis VADER (modo degradado, sin DeepSeek)",
        "opciones": [],
        "opciones_acciones": [],
        "fuente_fallback": f"vader::{moneda}",
    }


@router.get("/pronostico/{from_curr}/{to_curr}")
async def get_pronostico(from_curr: str, to_curr: str, dias: int = Query(80)):
    """Pronóstico ARIMA a 5 días + señal estadística ARMA sobre rendimientos."""
    try:
        historico = await obtener_historico_par(from_curr.upper(), to_curr.upper(), dias)
        if historico is None or len(historico) < 30:
            return {"error": f"No se pudo obtener historico para {from_curr}/{to_curr}"}, 503
        valores = [p["precio"] for p in historico]
        pron = pronostico_arima(valores)
        if pron is None:
            return {"error": "No hay suficientes datos para el pronostico"}, 503
        pron["senal_estadistica"] = senal_arma_desde_precios(valores)
        pron["timestamp"] = datetime.utcnow().isoformat()
        return {"success": True, "from": from_curr.upper(), "to": to_curr.upper(), **pron}
    except Exception as e:
        print(f"Error pronostico {from_curr}/{to_curr}: {e}")
        return {"error": "No se pudo calcular el pronostico"}, 503


@router.get("/analisis")
async def get_analisis(moneda: str = Query("USD")):
    """Analiza una moneda: sentimiento DeepSeek + semáforo basado en noticias.

    Args:
        moneda: código de la divisa (default USD).
    Returns:
        ``{"moneda", "precio", "cambio", "analisis_deepseek", "semaforo", ...}``.
    """
    moneda = moneda.upper()
    monedas = await obtener_precios_forex()
    if monedas is None:
        return {"error": "No se pudieron obtener precios Forex"}, 503
    data = monedas.get(moneda)
    if not data:
        return {"error": f"Moneda {moneda} no soportada"}, 404

    analisis = await analizar_sentimiento(moneda, data["precio"], data["cambio"])

    query = f"{moneda} forex OR {moneda} trading OR {moneda} currency"
    noticias = await obtener_noticias(query=query, cantidad=10)
    semaforo = await analizar_semaforo(moneda, noticias) if noticias else None

    db = get_db()
    if db is not None:
        try:
            await insert_dual("analisis", {
                "moneda": moneda,
                "precio": data["precio"],
                "cambio": data["cambio"],
                "analisis_deepseek": analisis,
                "semaforo": semaforo,
                "timestamp": datetime.utcnow(),
            })
        except Exception as e:
            print(f"Error DB insert analisis: {e}")

    return {
        "moneda": moneda,
        "precio": data["precio"],
        "cambio": data["cambio"],
        "analisis_deepseek": analisis,
        "semaforo": semaforo,
        "noticias_analizadas": len(noticias) if noticias else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.post("/analizar_historico")
async def post_analizar_historico(data: dict = Body(...)):
    """Analiza una simulación completa con DeepSeek (veredicto final).

    Recibe el histórico de precios y las métricas de la simulación, calcula el
    pronóstico ARIMA/ARMA, envía todo a DeepSeek y guarda el análisis cifrado.

    Returns:
        ``{"moneda", "analisis", "pronostico", "senal_estadistica", "timestamp"}``.
    """
    moneda = data.get("moneda", "USD").upper()
    precios = data.get("precios", [])
    capital_inicial = data.get("capital_inicial", 0)
    capital_final = data.get("capital_final", 0)
    rendimiento = data.get("rendimiento", 0)
    sharpe = data.get("sharpe", 0)
    drawdown = data.get("drawdown", 0)
    win_rate = data.get("win_rate", 0)

    vader = data.get("vader")

    if not precios:
        return {"error": "No hay datos historicos"}, 400

    tipos_cambio = None
    try:
        precios_fx = await obtener_precios_forex()
        if precios_fx:
            tasas = {}
            for a in ["USD", "EUR", "JPY"]:
                for b in ["MXN"]:
                    pa = precios_fx.get(a, {}).get("precio")
                    pb = precios_fx.get(b, {}).get("precio")
                    if pa and pb:
                        tasas[f"{a}/{b}"] = round(pa / pb, 6)
            for a, b in [("EUR", "USD"), ("USD", "JPY"), ("EUR", "JPY")]:
                pa = precios_fx.get(a, {}).get("precio")
                pb = precios_fx.get(b, {}).get("precio")
                if pa and pb:
                    tasas[f"{a}/{b}"] = round(pa / pb, 6)
            tipos_cambio = tasas
    except Exception as e:
        print(f"Error obteniendo tipos de cambio: {e}")

    acciones = None
    try:
        acciones = await obtener_acciones()
        if acciones:
            acciones = acciones[:220]
    except Exception as e:
        print(f"Error obteniendo acciones: {e}")

    pronostico_ctx = None
    senal_stat_ctx = None
    try:
        valores_p = [p["precio"] for p in precios]
        pronostico_ctx = pronostico_arima(valores_p)
        senal_stat_ctx = senal_arma_desde_precios(valores_p)
    except Exception as e:
        print(f"Error ARIMA/ARMA: {e}")

    analisis = await analizar_historico(
        moneda, precios, capital_inicial, capital_final, rendimiento,
        sharpe, drawdown, win_rate, vader, tipos_cambio, acciones,
        pronostico_ctx, senal_stat_ctx
    )
    if analisis is None:
        print(f"DeepSeek no disponible para {moneda}, usando fallback VADER")
        analisis = _fallback_vader(moneda, rendimiento, sharpe, vader)
    if analisis is None:
        return {"error": "No se pudo obtener analisis (DeepSeek ni VADER disponibles)"}, 503

    db = get_db()
    if db is not None:
        try:
            await insert_dual("analisis_historico", {
                "moneda": moneda,
                "precios_muestra": precios[:5],
                "total_datos": len(precios),
                "rendimiento": rendimiento,
                "sharpe": sharpe,
                "drawdown": drawdown,
                "win_rate": win_rate,
                "vader_enc": encrypt_text(json.dumps(vader)) if vader else None,
                "analisis_deepseek_enc": encrypt_text(json.dumps(analisis)),
                "timestamp": datetime.utcnow(),
            })
        except Exception as e:
            print(f"Error DB insert analisis_historico: {e}")

    return {
        "moneda": moneda,
        "analisis": analisis,
        "pronostico": pronostico_ctx,
        "senal_estadistica": senal_stat_ctx,
        "timestamp": datetime.utcnow().isoformat(),
    }
