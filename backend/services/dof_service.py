"""Servicio del tipo de cambio oficial del DOF (Diario Oficial de la Federacion).

Consulta la pagina de indicadores del DOF y extrae (mediante expresiones
regulares) la fecha de publicacion y el valor del dolar en pesos mexicanos.
"""
import httpx
import re
from datetime import datetime

DOF_URL = "https://www.dof.gob.mx/indicadores.php"


async def obtener_tipo_cambio_dolar() -> dict | None:
    """Obtiene el tipo de cambio del dolar publicado en el DOF.

    Returns:
        ``{"moneda_base", "moneda_cotizacion", "valor", "fecha", "fuente"}``
        o ``None`` si la pagina no responde o no se encuentra el valor.
    """
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(DOF_URL)
            if resp.status_code != 200:
                return None
    except Exception:
        return None

    texto = resp.text

    fecha_match = re.search(r"Tipo de Cambio y Tasas al\s*(\d{2}/\d{2}/\d{4})", texto)
    fecha = fecha_match.group(1) if fecha_match else datetime.now().strftime("%d/%m/%Y")

    valor_match = re.search(r"DOLAR\s*(?:</?\w+[^>]*>)*\s*([\d.]+)", texto)
    if not valor_match:
        return None

    try:
        valor = float(valor_match.group(1))
    except ValueError:
        return None

    return {
        "moneda_base": "USD",
        "moneda_cotizacion": "MXN",
        "valor": valor,
        "fecha": fecha,
        "fuente": "DOF (Banco de México)",
    }
