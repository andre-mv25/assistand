"""Servicio de datos de mercado via Yahoo Finance (libreria ``yfinance``).

Provee cotizaciones Forex en tiempo real, historicos de precios y calculo de
pares de divisas (incluida la tasa cruzada cuando ninguna moneda es el USD).
Las funciones ``_sincrono_*`` ejecutan la libreria bloqueante en un hilo y las
funciones ``async`` las envuelven para usarse con FastAPI/Motor.
"""
import asyncio
import yfinance as yf
from datetime import datetime, timedelta

PARES_FOREX = {
    "USD": {"ticker": "USD=X", "invertir": False, "decimales": 4},
    "MXN": {"ticker": "USDMXN=X", "invertir": True, "decimales": 6},
    "JPY": {"ticker": "USDJPY=X", "invertir": True, "decimales": 6},
    "EUR": {"ticker": "EURUSD=X", "invertir": False, "decimales": 4},
}

def _sincrono_obtener_precios():
    """Descarga cotizaciones del dia (intervalo 1 min) para USD, MXN, JPY y EUR.

    Devuelve un diccionario con ``{"precio": ..., "cambio": ...}`` por moneda,
    o ``None`` si la descarga falla. El USD se define como referencia (1.0).
    """
    tickers = [v["ticker"] for v in PARES_FOREX.values() if v["ticker"] != "USD=X"]
    data = yf.download(tickers, period="1d", interval="1m", progress=False)
    if data is None or data.empty:
        return None
    resultados = {}
    for moneda, cfg in PARES_FOREX.items():
        if moneda == "USD":
            resultados[moneda] = {"precio": 1.0, "cambio": 0.0}
            continue
        try:
            precios = data["Close"]
            if hasattr(precios, "columns"):
                close_series = precios[cfg["ticker"]].dropna()
            else:
                close_series = precios.dropna()
            ultimo = float(close_series.iloc[-1]) if not close_series.empty else None
            primero = float(close_series.iloc[0]) if not close_series.empty else None
        except (IndexError, KeyError, AttributeError):
            return None
        if ultimo is None or ultimo == 0:
            return None
        if cfg["invertir"]:
            ultimo = 1.0 / ultimo
            if primero and primero > 0:
                primero = 1.0 / primero
        cambio = ((ultimo - primero) / primero * 100) if primero and primero > 0 else 0.0
        resultados[moneda] = {
            "precio": round(ultimo, cfg["decimales"]),
            "cambio": round(cambio, 2),
        }
    return resultados

def _sincrono_obtener_historico(moneda: str, dias: int = 30):
    """Obtiene el historico diario de cierre de una moneda (en USD por unidad).

    Args:
        moneda: codigo (USD, MXN, JPY, EUR).
        dias: cantidad de dias hacia atras.
    Returns:
        Lista de ``{"fecha": YYYY-MM-DD, "precio": float}`` o ``None`` si falla.
    """
    cfg = PARES_FOREX.get(moneda.upper())
    if not cfg or moneda.upper() == "USD":
        return None
    data = yf.download(cfg["ticker"], period=f"{dias}d", interval="1d", progress=False)
    if data is None or data.empty:
        return None
    close_col = data["Close"]
    if hasattr(close_col, "columns") and len(close_col.columns) > 0:
        close_series = close_col.iloc[:, 0]
    else:
        close_series = close_col
    resultado = []
    for fecha, precio_val in close_series.items():
        precio = float(precio_val)
        if cfg["invertir"] and precio > 0:
            precio = 1.0 / precio
        resultado.append({
            "fecha": fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha),
            "precio": round(precio, cfg["decimales"]),
        })
    return resultado if resultado else None


async def obtener_precios_forex():
    """Devuelve las cotizaciones Forex actuales (envuelve la llamada bloqueante)."""
    return await asyncio.to_thread(_sincrono_obtener_precios)

async def obtener_historico_forex(moneda: str, dias: int = 30):
    """Devuelve el historico diario de una moneda (envuelve la llamada bloqueante)."""
    return await asyncio.to_thread(_sincrono_obtener_historico, moneda, dias)


def _calcular_par(from_curr: str, to_curr: str, precios: dict):
    """Calcula la tasa FROM/TO a partir de las cotizaciones en USD de ambas."""
    usd_from = precios.get(from_curr, {}).get("precio")
    usd_to = precios.get(to_curr, {}).get("precio")
    if not usd_from or not usd_to:
        return None
    return usd_from / usd_to


def _sincrono_obtener_historico_par(from_curr: str, to_curr: str, dias: int = 30):
    """Obtiene el historico diario de un par de divisas FROM/TO.

    Si una moneda es el USD usa el ticker directo; si ambas son no-USD calcula
    la tasa cruzada combinando los dos historicos por fecha.
    """
    cfg_from = PARES_FOREX.get(from_curr)
    cfg_to = PARES_FOREX.get(to_curr)
    if not cfg_from or not cfg_to:
        return None

    # USD involucrado: usar el ticker directo de la otra moneda
    if from_curr == "USD":
        hist = _sincrono_obtener_historico(to_curr, dias)
        if not hist:
            return None
        return [{"fecha": p["fecha"], "precio": round(1.0 / p["precio"], 6)} for p in hist if p["precio"] > 0]

    if to_curr == "USD":
        hist = _sincrono_obtener_historico(from_curr, dias)
        return hist  # Ya está en USD por unidad de la moneda FROM

    # Ambos no-USD: descargar ambos y calcular tasa cruzada
    data_from = yf.download(cfg_from["ticker"], period=f"{dias}d", interval="1d", progress=False)
    data_to = yf.download(cfg_to["ticker"], period=f"{dias}d", interval="1d", progress=False)
    if data_from is None or data_to is None or data_from.empty or data_to.empty:
        return None

    def extraer_serie(data, cfg):
        close_col = data["Close"]
        if hasattr(close_col, "columns") and len(close_col.columns) > 0:
            series = close_col.iloc[:, 0]
        else:
            series = close_col
        result = {}
        for fecha, valor in series.items():
            precio = float(valor)
            if cfg["invertir"] and precio > 0:
                precio = 1.0 / precio
            result[fecha.strftime("%Y-%m-%d") if hasattr(fecha, "strftime") else str(fecha)] = precio
        return result

    usd_from = extraer_serie(data_from, cfg_from)
    usd_to = extraer_serie(data_to, cfg_to)

    resultado = []
    for fecha in usd_from:
        if fecha in usd_to and usd_to[fecha] > 0:
            resultado.append({
                "fecha": fecha,
                "precio": round(usd_from[fecha] / usd_to[fecha], 6),
            })
    return resultado if resultado else None


async def obtener_precio_par(from_curr: str, to_curr: str):
    """Devuelve la tasa actual del par FROM/TO con su marca de tiempo.

    Returns:
        ``{"from", "to", "rate", "timestamp"}`` o ``None`` si no se pudo calcular.
    """
    precios = await obtener_precios_forex()
    if not precios:
        return None
    rate = _calcular_par(from_curr.upper(), to_curr.upper(), precios)
    if rate is None:
        return None
    return {
        "from": from_curr.upper(),
        "to": to_curr.upper(),
        "rate": round(rate, 6),
        "timestamp": datetime.utcnow().isoformat(),
    }


async def obtener_historico_par(from_curr: str, to_curr: str, dias: int = 30):
    """Devuelve el historico diario del par FROM/TO (envuelve la llamada bloqueante)."""
    return await asyncio.to_thread(_sincrono_obtener_historico_par, from_curr.upper(), to_curr.upper(), dias)
