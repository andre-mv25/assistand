import json as js
import httpx
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL


async def analizar_sentimiento(moneda: str, precio: float, cambio: float):
    if not DEEPSEEK_API_KEY:
        return None

    prompt = f"""
Eres un analista financiero experto. Analiza el sentimiento del mercado para {moneda}.
Precio actual: {precio:.2f}
Cambio: {cambio:.2f}%

Responde UNICAMENTE con un JSON valido sin markdown:
{{
  "sentimiento": "alcista" | "bajista" | "neutral",
  "valor": -1 a 1,
  "analisis": "breve explicacion (max 2 oraciones)",
  "recomendacion": "COMPRAR" | "VENDER" | "MANTENER",
  "confianza": 0 a 1
}}
"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Eres un analista financiero. Responde solo JSON valido, sin markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 300,
            },
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        inicio = content.find("{")
        fin = content.rfind("}")
        if inicio == -1 or fin == -1:
            return None
        return js.loads(content[inicio:fin+1])


async def analizar_semaforo(moneda: str, noticias: list):
    if not DEEPSEEK_API_KEY or not noticias:
        return None

    noticias_texto = "\n".join(
        f"- [{n.get('fuente', '?')}] {n.get('titulo', '')}: {n.get('descripcion', '')}"
        for n in noticias[:15]
    )

    prompt = f"""
Eres un analista financiero experto en forex. Analiza las siguientes noticias recientes y determina si es buen momento para COMPRAR {moneda}.

NOTICIAS RECIENTES:
{noticias_texto}

Responde UNICAMENTE con un JSON valido sin markdown:
{{
  "semaforo": "verde" | "amarillo" | "rojo",
  "sentimiento": "alcista" | "bajista" | "neutral",
  "confianza": 0.85,
  "explicacion": "breve explicacion del porque (max 2 oraciones)",
  "noticias_clave": ["titulo noticia mas relevante 1", "titulo noticia mas relevante 2"]
}}
"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "Eres un analista financiero. Responde solo JSON valido, sin markdown."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 400,
            },
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        inicio = content.find("{")
        fin = content.rfind("}")
        if inicio == -1 or fin == -1:
            return None
        return js.loads(content[inicio:fin+1])
