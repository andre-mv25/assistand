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
    if not BANXICO_API_KEY:
        return None

    serie = SERIES_TIPO_CAMBIO.get(moneda.upper())
    if not serie:
        return None

    hoy = fecha or datetime.now().strftime("%Y-%m-%d")
    url = f"{BANXICO_BASE_URL}/series/{serie}/datos/{hoy}/{hoy}"

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
    if not BANXICO_API_KEY:
        return None

    lista = monedas or list(SERIES_TIPO_CAMBIO.keys())
    resultados = {}
    for m in lista:
        tc = await obtener_tipo_cambio(m)
        if tc:
            resultados[m] = tc
    return resultados if resultados else None
