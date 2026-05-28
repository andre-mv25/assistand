import asyncio
import yfinance as yf
from datetime import datetime, timedelta

PARES_FOREX = {
    "USD": {"ticker": "USD=X", "invertir": False, "decimales": 4},
    "MXN": {"ticker": "USDMXN=X", "invertir": False, "decimales": 4},
    "JPY": {"ticker": "USDJPY=X", "invertir": False, "decimales": 3},
    "EUR": {"ticker": "EURUSD=X", "invertir": True, "decimales": 4},
}

def _sincrono_obtener_precios():
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
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sincrono_obtener_precios)

async def obtener_historico_forex(moneda: str, dias: int = 30):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _sincrono_obtener_historico, moneda, dias
    )
