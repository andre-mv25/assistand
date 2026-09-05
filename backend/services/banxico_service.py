"""Servicio de tipo de cambio oficial via API del Banco de Mexico (Banxico).

Consulta las series FIX de tipo de cambio (USD, EUR, JPY) publicadas por
Banxico y devuelve el ultimo valor observado para cada moneda.
"""
import httpx
from datetime import datetime
from config import BANXICO_API_KEY

BANXICO_BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1"

# Series oficiales de tipo de cambio FIX (Banco de México)
SERIES_TIPO_CAMBIO = {
    "USD": "SF43718",   # Dólar (pesos por dólar)
    "EUR": "SF46410",   # Euro (pesos por euro)
    "JPY": "SF46406",   # Yen japonés (pesos por yen)
}


async def obtener_tipo_cambio(moneda: str = "USD", fecha: str | None = None) -> dict | None:
    """Obtiene el tipo de cambio oficial FIX de una moneda.

    Args:
        moneda: USD, EUR o JPY.
        fecha: fecha en formato YYYY-MM-DD (por defecto la de hoy).
    Returns:
        ``{"moneda", "valor", "fecha", "fuente", "serie"}`` o ``None`` si falla.
    """
    if not BANXICO_API_KEY:
        return None

    serie = SERIES_TIPO_CAMBIO.get(moneda.upper())
    if not serie:
        return None

    hoy = fecha or datetime.now().strftime("%Y-%m-%d")
    rango = f"{hoy}/{hoy}" if fecha else "oportuno"
    url = f"{BANXICO_BASE_URL}/series/{serie}/datos/{rango}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params={"token": BANXICO_API_KEY})
            if resp.status_code != 200:
                return None
            data = resp.json()
    except Exception:
        return None

    try:
        serie_data = data["bmx"]["series"][0]
        observaciones = serie_data.get("datos", [])
        if not observaciones:
            return None
        obs = observaciones[-1]
        valor = obs.get("dato")
        if valor in (None, "", "N/E"):
            return None
        return {
            "moneda": moneda.upper(),
            "valor": float(valor),
            "fecha": obs.get("fecha", hoy),
            "fuente": "Banxico (Banco de México)",
            "serie": serie_data.get("idSerie", serie),
        }
    except (KeyError, IndexError, ValueError, TypeError):
        return None


async def obtener_tipo_cambio_multiples(monedas: list[str] | None = None) -> dict | None:
    """Obtiene el tipo de cambio FIX de varias monedas a la vez.

    Args:
        monedas: lista de codigos; por defecto todas las series definidas.
    Returns:
        Diccionario ``{codigo: resultado}`` o ``None`` si no hay resultados.
    """
    if not BANXICO_API_KEY:
        return None

    lista = monedas or list(SERIES_TIPO_CAMBIO.keys())
    resultados = {}
    for m in lista:
        tc = await obtener_tipo_cambio(m)
        if tc:
            resultados[m] = tc
    return resultados if resultados else None
