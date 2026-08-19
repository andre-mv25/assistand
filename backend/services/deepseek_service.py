import json as js
import time
import hashlib
import asyncio
import httpx
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL

# ============ PROTECCIONES ============

_cache = {}
CACHE_TTL = 600  # 10 minutos

_rate_times = []
RATE_MAX = 6          # max llamadas
RATE_WINDOW = 60      # por minuto
_rate_lock = asyncio.Lock()

_fallos_consecutivos = 0
CIRCUITO_UMBRAL = 3
CIRCUITO_ESPERA = 60
_circuito_abierto_hasta = 0.0

TIMEOUT_LLAMADA = 20  # segundos
RETRIES = 3


def _clave_cache(nombre, *args):
    serial = js.dumps(args, default=str, sort_keys=True)
    return hashlib.md5(f"{nombre}|{serial}".encode()).hexdigest()


def _leer_cache(clave):
    item = _cache.get(clave)
    if not item:
        return None
    if time.time() - item["ts"] > CACHE_TTL:
        _cache.pop(clave, None)
        return None
    return item["data"]


def _escribir_cache(clave, data):
    _cache[clave] = {"ts": time.time(), "data": data}
    if len(_cache) > 200:
        ahora = time.time()
        viejos = [k for k, v in _cache.items() if ahora - v["ts"] > CACHE_TTL]
        for k in viejos:
            _cache.pop(k, None)


def _circuito_abierto():
    return time.time() < _circuito_abierto_hasta


def _registrar_fallo():
    global _fallos_consecutivos, _circuito_abierto_hasta
    _fallos_consecutivos += 1
    if _fallos_consecutivos >= CIRCUITO_UMBRAL:
        _circuito_abierto_hasta = time.time() + CIRCUITO_ESPERA
        print(f"DeepSeek: circuito abierto por {CIRCUITO_ESPERA}s (fallos consecutivos: {_fallos_consecutivos})")


def _registrar_exito():
    global _fallos_consecutivos, _circuito_abierto_hasta
    _fallos_consecutivos = 0
    _circuito_abierto_hasta = 0.0


async def _permitido_rate_limit():
    global _rate_times
    async with _rate_lock:
        ahora = time.time()
        _rate_times = [t for t in _rate_times if ahora - t < RATE_WINDOW]
        if len(_rate_times) >= RATE_MAX:
            return False
        _rate_times.append(ahora)
        return True


def _normalizar(resultado):
    for key in resultado:
        if isinstance(resultado[key], str):
            resultado[key] = (
                resultado[key]
                .replace("alcista", "alta").replace("bajista", "baja")
                .replace("positivo", "alta").replace("negativo", "baja")
                .replace("Alcista", "Alta").replace("Bajista", "Baja")
                .replace("Positivo", "Alta").replace("Negativo", "Baja")
            )
    return resultado


async def _llamar_deepseek(prompt: str, max_tokens: int):
    """Llama a la API de DeepSeek con cache, rate limit, reintentos y circuito."""
    if not DEEPSEEK_API_KEY:
        return None

    if _circuito_abierto():
        print("DeepSeek: circuito abierto, saltando llamada")
        return None

    permitido = await _permitido_rate_limit()
    if not permitido:
        print("DeepSeek: rate limit alcanzado")
        return None

    ultimo_error = None
    for intento in range(RETRIES):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_LLAMADA) as client:
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
                        "max_tokens": max_tokens,
                    },
                )
        except (httpx.TimeoutException, httpx.NetworkError, httpx.ConnectError) as e:
            ultimo_error = e
            if intento < RETRIES - 1:
                print(f"DeepSeek: error de red (intento {intento + 1}/{RETRIES}): {e}")
                await asyncio.sleep(2 ** intento)
                continue
            break

        if resp.status_code == 200:
            try:
                content = resp.json()["choices"][0]["message"]["content"]
                inicio = content.find("{")
                fin = content.rfind("}")
                if inicio == -1 or fin == -1:
                    ultimo_error = "Respuesta sin JSON"
                    break
                resultado = js.loads(content[inicio:fin + 1])
                _registrar_exito()
                return _normalizar(resultado)
            except (js.JSONDecodeError, KeyError, IndexError) as e:
                ultimo_error = e
                break

        if resp.status_code == 429:
            ultimo_error = f"Rate limit HTTP {resp.status_code}"
            if intento < RETRIES - 1:
                print(f"DeepSeek: rate limit, reintentando en {2 ** intento}s")
                await asyncio.sleep(2 ** intento)
                continue
            break

        if resp.status_code in (500, 502, 503):
            ultimo_error = f"Error de servidor HTTP {resp.status_code}"
            if intento < RETRIES - 1:
                await asyncio.sleep(2 ** intento)
                continue
            break

        ultimo_error = f"HTTP {resp.status_code}"
        break

    _registrar_fallo()
    print(f"DeepSeek: llamada fallida tras {RETRIES} intentos: {ultimo_error}")
    return None


async def _analizar_con_cache(nombre: str, clave_args: tuple, prompt: str, max_tokens: int):
    clave = _clave_cache(nombre, *clave_args)
    desde_cache = _leer_cache(clave)
    if desde_cache is not None:
        print(f"DeepSeek: respuesta desde cache ({nombre})")
        return desde_cache
    resultado = await _llamar_deepseek(prompt, max_tokens)
    if resultado is not None:
        _escribir_cache(clave, resultado)
    return resultado


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
    return await _analizar_con_cache("sentimiento", (moneda, precio, cambio), prompt, 300)


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
    return await _analizar_con_cache("semaforo", (moneda, noticias_texto[:500]), prompt, 400)


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

ESTILO DE ESCRITURA: Escribe como un asesor que le habla a una persona sin experiencia en bolsa: frases cortas, sin tecnicismos innecesarios, y si mencionas un numero (rendimiento, drawdown, RSI, SMA, Sharpe) di en una frase sencilla que significa para el usuario.

Responde UNICAMENTE con un JSON valido sin markdown:
{{
  "sentimiento": "alta" | "baja" | "neutral",
  "valor": -1 a 1,
  "analisis": "analisis breve en lenguaje CLARO Y SENCILLO, de maximo 3 oraciones, como si se lo explicaras a un principiante: di que paso con el dinero, que indican los numeros clave y que recomiendas. Evita jerga; si usas un termino tecnico, explica su significado en la misma frase",
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
    return await _analizar_con_cache(
        "historico",
        (moneda, round(precio_inicial, 4), round(precio_final, 4), round(rendimiento, 2), round(sharpe, 2), round(drawdown, 1), round(win_rate, 1)),
        prompt,
        2500,
    )