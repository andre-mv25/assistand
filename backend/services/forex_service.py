"""Servicio alternativo de tipo de cambio via Frankfurter (BCE).

Consulta la API de Frankfurter (basada en el Banco Central Europeo) para
cotizaciones actuales e historicos de divisas frente al USD.
"""
import httpx
from datetime import datetime, timedelta
from config import FRANKFURTER_BASE_URL


async def obtener_precios_forex():
    """Obtiene las cotizaciones actuales de JPY, EUR y MXN frente al USD."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{FRANKFURTER_BASE_URL}/latest",
            params={"from": "USD", "to": "JPY,EUR,MXN"}
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        rates = data.get("rates", {})
        if not rates:
            return None
        return {
            "USD": {"precio": 1.0, "cambio": 0.0},
            "JPY": {"precio": rates.get("JPY"), "cambio": 0.0},
            "EUR": {"precio": rates.get("EUR"), "cambio": 0.0},
            "MXN": {"precio": rates.get("MXN"), "cambio": 0.0},
        }


async def obtener_historico_forex(moneda: str, dias: int = 30):
    """Obtiene el historico diario de una moneda frente al USD.

    Args:
        moneda: codigo de la divisa (JPY, EUR, MXN...).
        dias: cantidad de dias hacia atras.
    Returns:
        Lista de ``{"fecha", "precio"}`` o ``None`` si falla.
    """
    hoy = datetime.utcnow()
    inicio = hoy - timedelta(days=dias)
    periodo = f"{inicio.strftime('%Y-%m-%d')}..{hoy.strftime('%Y-%m-%d')}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{FRANKFURTER_BASE_URL}/{periodo}",
            params={"from": "USD", "to": moneda}
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        rates = data.get("rates", {})
        if not rates:
            return None
        return [{"fecha": k, "precio": v.get(moneda)} for k, v in rates.items()]
