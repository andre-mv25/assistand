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
        resultado = js.loads(content[inicio:fin+1])
        for key in ["sentimiento", "analisis", "recomendacion"]:
            if key in resultado and isinstance(resultado[key], str):
                resultado[key] = resultado[key].replace("alcista", "alta").replace("bajista", "baja").replace("positivo", "alta").replace("negativo", "baja").replace("Alcista", "Alta").replace("Bajista", "Baja").replace("Positivo", "Alta").replace("Negativo", "Baja")
        return resultado

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
        resultado = js.loads(content[inicio:fin+1])
        for key in ["sentimiento", "analisis", "recomendacion"]:
            if key in resultado and isinstance(resultado[key], str):
                resultado[key] = resultado[key].replace("alcista", "alta").replace("bajista", "baja").replace("positivo", "alta").replace("negativo", "baja").replace("Alcista", "Alta").replace("Bajista", "Baja").replace("Positivo", "Alta").replace("Negativo", "Baja")
        return resultado


async def analizar_historico(moneda: str, precios: list[dict], capital_inicial: float, capital_final: float, rendimiento: float, sharpe: float, drawdown: float, win_rate: float, vader: dict | None = None, tipos_cambio: dict | None = None, acciones: list | None = None):
    if not DEEPSEEK_API_KEY or not precios:
        return None

    valores = [p["precio"] for p in precios]

    # --- INDICADORES TÉCNICOS ---
    def sma(data, periodo):
        if len(data) < periodo: return None
        return sum(data[-periodo:]) / periodo

    def rsi(data, periodo=14):
        if len(data) < periodo + 1: return None
        ganancias = sum(max(data[i] - data[i-1], 0) for i in range(-periodo, 0))
        perdidas = sum(max(data[i-1] - data[i], 0) for i in range(-periodo, 0))
        if perdidas == 0: return 100
        rs = ganancias / perdidas
        return 100 - (100 / (1 + rs))

    def volatilidad(data):
        if len(data) < 2: return 0
        returns = [(data[i] - data[i-1]) / data[i-1] for i in range(1, len(data))]
        media = sum(returns) / len(returns)
        varianza = sum((r - media) ** 2 for r in returns) / len(returns)
        return varianza ** 0.5

    precio_inicial = valores[0]
    precio_final = valores[-1]
    tendencia_pct = ((precio_final - precio_inicial) / precio_inicial) * 100
    sma5 = sma(valores, 5)
    sma20 = sma(valores, 20)
    cruce_sma = "ninguno"
    if sma5 and sma20:
        if sma5 > sma20: cruce_sma = "SMA5 sobre SMA20 (tendencia positiva)"
        else: cruce_sma = "SMA5 bajo SMA20 (tendencia negativa)"
    rsi_val = rsi(valores)
    vol = volatilidad(valores)

    sma5_str = f"{sma5:.4f}" if sma5 else "N/A"
    sma20_str = f"{sma20:.4f}" if sma20 else "N/A"
    rsi_str = f"{rsi_val:.1f}" if rsi_val else "N/A"
    indicadores = f"""
INDICADORES TECNICOS CALCULADOS:
- Tendencia del periodo: {tendencia_pct:+.2f}%
- SMA5: {sma5_str} | SMA20: {sma20_str}
- Cruce SMA: {cruce_sma}
- RSI (14): {rsi_str} (sobrecompra > 70, sobreventa < 30)
- Volatilidad diaria: {vol*100:.2f}%
"""
    # --- NOTICIAS REALES ---
    noticias_context = ""
    if vader and vader.get("noticias"):
        noticias_lista = vader["noticias"]
        noticias_texto = "\n".join(
            f"- [{n.get('fuente', '?')}] {n.get('titulo', '')}"
            for n in noticias_lista[:8]
        )
        noticias_context = f"""
NOTICIAS FINANCIERAS RECIENTES:
{noticias_texto}
"""
    # --- TIPOS DE CAMBIO Y SEMAFORO ---
    tc_context = ""
    if tipos_cambio:
        tc_lineas = "\n".join(f"- {par}: {rate}" for par, rate in tipos_cambio.items())
        tc_context = f"""
TIPOS DE CAMBIO ACTUALES:
{tc_lineas}
"""
    semaforo_context = ""
    if vader:
        label = vader.get("clasificacion", "neutral")
        semaforo_context = f"""
SEMAFORO DE INVERSION (VADER sobre {vader.get('noticias_analizadas', 0)} noticias):
- Compound score: {vader.get('compound_score', 'N/A')}
- Clasificacion: {label.upper()} (>= 0.05 = COMPRAR, <= -0.05 = VENDER, si no MANTENER)
"""
    acciones_context = ""
    if acciones:
        lineas = "\n".join(
            f"- {a['ticker']}|{a['empresa']}|${a['precio']}|dia{a['cambio_dia']:+.1f}%|mom{a['momentum_60d']:+.1f}%|vol{a['volatilidad_anual']:.0f}%|RSI{a['rsi']}|score{a['score']}"
            for a in acciones
        )
        acciones_context = f"""
ACCIONES CANDIDATAS (universo amplio de empresas con datos reales de mercado de los ultimos 90 dias; formato: ticker|empresa|precio|cambio dia|momentum 60d|volatilidad anual|RSI|score retorno/riesgo):
{lineas}
"""
    # --- CADENA DE PENSAMIENTO ---
    prompt = f"""
Eres un analista financiero experto. Analiza la siguiente simulacion historica de {moneda}.
{noticias_context}
DATOS DE LA SIMULACION:
{len(precios)} datos, rango: {precios[0]["fecha"]} a {precios[-1]["fecha"]}
Precio inicial: {precio_inicial:.4f}
Precio final: {precio_final:.4f}
Capital inicial (monto invertido): ${capital_inicial:,.2f}
Capital final: ${capital_final:,.2f}
Rendimiento: {rendimiento:.2f}%
Sharpe Ratio: {sharpe:.2f}
Max Drawdown: {drawdown:.1f}%
Win Rate: {win_rate:.1f}%
{indicadores}
{tc_context}
{semaforo_context}
{acciones_context}
ANTES DE RESPONDER, RAZONA PASO A PASO:
1. Analiza la tendencia del precio: {tendencia_pct:+.2f}% en el periodo. ¿Es positiva, negativa o neutral?
2. Revisa los indicadores tecnicos: SMA5/SMA20 ({cruce_sma}), RSI ({rsi_str}), volatilidad ({vol*100:.2f}%). ¿Se refuerzan entre si o hay divergencia?
3. Compara con las noticias: ¿el sentimiento de las noticias (VADER: {vader.get('compound_score', 'N/A') if vader else 'N/A'}) confirma o contradice los datos tecnicos?
4. Integra los tipos de cambio actuales: ¿que moneda se ve mas fuerte o mas barata frente a MXN?
5. Concluye: con toda la informacion integrada, ¿que recomiendas?
6. GENERA 3 A 5 OPCIONES DE INVERSION EN DIVISAS: para cada una indica que hacer con el capital (monto disponible ${capital_inicial:,.2f}), que moneda comprar o en cual mantenerse, el par involucrado, el riesgo y el retorno esperado estimado, justificando con los datos de la grafica (tendencia, SMA, RSI, volatilidad), el semaforo y los tipos de cambio actuales.
7. GENERA 3 A 5 OPCIONES DE COMPRA DE ACCIONES (MAXIMO 5, nunca mas): TÚ decides cuales convienen mas para maximizar la ganancia del inversionista. Elige unicamente dentro del universo de ACCIONES CANDIDATAS las que mejor combinen mayor score retorno/riesgo, mayor momentum, menor volatilidad y RSI saludable (no sobrecomprado), congruentes con el semaforo y las noticias. Prefiere variedad de sectores y paises. Para cada una indica cuanto capital invertir, el riesgo y el retorno esperado. Usa el ticker EXACTO tal como aparece en la lista.

VOCABULARIO OBLIGATORIO: Usa exclusivamente "alta" para tendencia positiva, "baja" para tendencia negativa, "neutral" para sin tendencia. NO uses las palabras alcista, bajista, positivo, negativo, bullish, bearish.

Responde UNICAMENTE con un JSON valido sin markdown:
{{
  "sentimiento": "alta" | "baja" | "neutral",
  "valor": -1 a 1,
  "analisis": "analisis integrando datos historicos, indicadores tecnicos y noticias (max 3 oraciones)",
  "recomendacion": "COMPRAR" | "VENDER" | "MANTENER",
  "confianza": 0 a 1,
  "patron_encontrado": "patron observado en los datos",
  "opciones": [
    {{
      "titulo": "titulo corto de la opcion",
      "accion": "que hacer exactamente con el capital (ej: convertir el 50% del monto a USD)",
      "par": "par involucrado (ej: USD/MXN)",
      "riesgo": "bajo" | "medio" | "alto",
      "retorno_esperado": "estimacion breve del retorno esperado",
      "razon": "por que elegir esta opcion integrando grafica, semaforo y tipos de cambio (max 2 oraciones)"
    }}
  ],
  "opciones_acciones": [
    {{
      "titulo": "titulo corto de la opcion (ej: Comprar AAPL)",
      "empresa": "nombre completo de la empresa",
      "ticker": "ticker (ej: AAPL)",
      "precio_actual": 0.0,
      "accion": "que hacer exactamente (ej: invertir el 20% del capital en acciones de Apple)",
      "riesgo": "bajo" | "medio" | "alto",
      "retorno_esperado": "estimacion breve del retorno esperado",
      "razon": "por que elegir esta accion basandote en score, momentum, volatilidad, RSI y semaforo (max 2 oraciones)"
    }}
  ]
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
                "max_tokens": 2500,
            },
        )
        if resp.status_code != 200:
            return None
        content = resp.json()["choices"][0]["message"]["content"]
        inicio = content.find("{")
        fin = content.rfind("}")
        if inicio == -1 or fin == -1:
            return None
        try:
            resultado = js.loads(content[inicio:fin+1])
        except js.JSONDecodeError:
            return None
        for key in resultado:
            if isinstance(resultado[key], str):
                resultado[key] = resultado[key].replace("alcista", "alta").replace("bajista", "baja").replace("positivo", "alta").replace("negativo", "baja").replace("Alcista", "Alta").replace("Bajista", "Baja").replace("Positivo", "Alta").replace("Negativo", "Baja")
        return resultado
