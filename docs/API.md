# Manual de la API REST — Trading Assistant

API construida con **FastAPI** (Python 3.13). Base URL en producción:
`https://assistand.onrender.com`. En desarrollo: `http://localhost:8000`.

- Todos los endpoints responden **JSON**.
- Documentación interactiva (Swagger UI): `http://localhost:8000/docs`.
- Errores: `{"error": "mensaje"}` con códigos HTTP 400/401/404/500/503.

---

## 1. Frontend y estado

### `GET /`
Sirve el frontend (`index.html`).

### `GET /api/test`
Prueba de vida de la API.
```json
{ "status": "ok", "timestamp": "..." }
```

### `GET /api/status`
Estado de la API y de la conexión a MongoDB (Atlas / local).
```json
{ "api": "online", "version": "1.0.0", "base_datos": "conectado",
  "base_datos_atlas": "conectado", "timestamp": "..." }
```

---

## 2. Precios y pares de divisas

### `GET /api/precios`
Cotizaciones Forex actuales de todas las monedas.
```json
{ "monedas": { "USD": {"precio": 1.0, "cambio": 0.0},
               "MXN": {"precio": 17.03, "cambio": -0.12}, ... },
  "timestamp": "..." }
```

### `GET /api/precios/{moneda}`
Cotización de una moneda concreta (`USD`, `MXN`, `JPY`, `EUR`).
```json
{ "moneda": "MXN", "precio": 17.03, "cambio": -0.12, "timestamp": "..." }
```

### `GET /api/par/{from}/{to}`
Tasa de cambio actual del par (ej. `/api/par/USD/MXN`).
```json
{ "from": "USD", "to": "MXN", "rate": 17.0312, "timestamp": "..." }
```

### `GET /api/historico/{moneda}?dias=30`
Histórico diario de una moneda frente al USD.
```json
{ "moneda": "JPY", "datos": [{"fecha": "2026-08-19", "precio": 0.0068}], "timestamp": "..." }
```

### `GET /api/historico_par/{from}/{to}?dias=60`
Histórico diario del par (alimenta la gráfica y la simulación).
```json
{ "from": "USD", "to": "MXN", "datos": [{"fecha": "2026-08-19", "precio": 17.03}], "timestamp": "..." }
```

### `GET /api/pronostico/{from}/{to}?dias=80`
Pronóstico **ARIMA** a 5 días con bandas de confianza (90%) y señal **ARMA**.
```json
{ "success": true, "from": "USD", "to": "MXN", "modelo": "ARIMA(0,1,1)",
  "ultimo_precio": 17.03,
  "pronostico": [17.01, 17.00, ...], "inferior": [...], "superior": [...],
  "cambio_pct": -0.1,
  "senal_estadistica": { "modelo": "ARMA(0,0,1)", "etiqueta": "NEUTRAL",
    "prediccion_pct": -0.03, "confianza": 0.15 },
  "timestamp": "..." }
```

---

## 3. Noticias y sentimiento

### `GET /api/noticias?query=forex&fuentes=reuters,cnbc&cantidad=10`
Busca noticias financieras en NewsAPI.
```json
{ "noticias": [ {"titulo": "...", "descripcion": "...", "fuente": "Reuters",
                 "url": "...", "imagen": "...", "fecha": "..."} ],
  "total": 10, "timestamp": "..." }
```

### `GET /api/noticias/portadas?categoria=business&pais=us&cantidad=5`
Portadas (top headlines) por categoría y país.

### `GET /api/vader?query=forex&cantidad=2000`
Sentimiento del mercado con **VADER** sobre noticias de varias fuentes.
```json
{ "compound_score": 0.12, "clasificacion": "alta",
  "noticias_analizadas": 120,
  "total_newsapi": 80, "total_google": 30, "total_gnews": 10,
  "source": "VADER (NewsAPI + Google News + GNews)", "noticias": [...] }
```

---

## 4. Análisis y semáforo

### `GET /api/analisis?moneda=USD`
Análisis completo de una moneda: DeepSeek + semáforo de noticias.
```json
{ "moneda": "USD", "precio": 1.0, "cambio": 0.0,
  "analisis_deepseek": { "sentimiento": "neutral", "valor": 0,
    "analisis": "...", "recomendacion": "MANTENER", "confianza": 0.5 },
  "semaforo": { "semaforo": "verde", "sentimiento": "alta", "confianza": 0.75,
    "explicacion": "...", "noticias_clave": ["..."] },
  "noticias_analizadas": 10, "timestamp": "..." }
```

### `POST /api/analizar_historico`
Analiza una simulación completa con DeepSeek y devuelve el veredicto final.

**Body (JSON):**
```json
{ "moneda": "USD", "precios": [{"fecha": "2026-08-19", "precio": 17.03}],
  "capital_inicial": 10000, "capital_final": 10420, "rendimiento": 4.2,
  "sharpe": 1.1, "drawdown": -2.5, "win_rate": 55, "vader": {...} }
```

**Respuesta:**
```json
{ "moneda": "USD",
  "analisis": { "sentimiento": "...", "valor": 0.4, "analisis": "...",
    "recomendacion": "COMPRAR", "confianza": 0.7, "patron_encontrado": "...",
    "opciones": [...], "opciones_acciones": [...] },
  "pronostico": {...}, "senal_estadistica": {...}, "timestamp": "..." }
```

---

## 5. Tipos de cambio oficiales

### `GET /api/dof/tipo_cambio`
Tipo de cambio del dólar publicado en el DOF (Diario Oficial de la Federación).
```json
{ "moneda_base": "USD", "moneda_cotizacion": "MXN", "valor": 17.03,
  "fecha": "19/08/2026", "fuente": "DOF (Banco de México)" }
```

### `GET /api/banxico/tipo_cambio?moneda=USD`
Tipo de cambio oficial **FIX** de Banxico para una moneda.

### `GET /api/banxico/tipo_cambio_all`
Tipos de cambio FIX de todas las monedas soportadas.

---

## 6. Cripto (CoinGecko)

### `GET /api/tendencias`
Criptomonedas más buscadas (trending).
```json
{ "tendencias": [ {"nombre": "Bitcoin", "simbolo": "BTC", ...} ], "timestamp": "..." }
```

---

## 7. Autenticación

### `POST /api/auth/register`
Registra un usuario. **Política de contraseña:** mínimo 8 caracteres, al menos
una mayúscula, un número y un carácter especial.

**Body:** `{ "username": "ana", "password": "Clave123!" }`

**Respuesta:** `{ "success": true, "message": "...", "token": "...", "username": "ana" }`

### `POST /api/auth/login`
Inicia sesión.

**Body:** `{ "username": "ana", "password": "Clave123!" }`

**Respuesta:** `{ "success": true, "message": "...", "token": "...", "username": "ana" }`

### `GET /api/auth/me?token=...`
Devuelve el usuario autenticado. `200` con `{ "success": true, "username": "ana" }`
o `401` si el token es inválido/expirado.

### `POST /api/auth/logout?token=...`
Cierra la sesión (elimina el documento de la sesión en la BD).

---

## 8. Simulaciones (historial por usuario)

Los tokens de sesión **caducan a los 30 días**. Los datos sensibles se guardan
**cifrados** (Fernet) y se descifran solo al momento de responder.

### `POST /api/simulaciones`
Guarda una simulación del usuario autenticado.

**Body (JSON):**
```json
{ "token": "...", "moneda": "USD", "monto": 10000,
  "capital_inicial": 10000, "capital_final": 10420, "rendimiento": 4.2,
  "sharpe": 1.1, "drawdown": -2.5, "win_rate": 55, "generado": 420,
  "compound": 4.2, "sentimiento": "alta", "recomendacion": "COMPRAR",
  "confianza": 0.7, "analisis": "..." }
```

**Respuesta:** `{ "success": true, "id": "<ObjectId>" }`

### `GET /api/simulaciones?token=...`
Lista el historial del usuario (hasta 50, ordenadas por fecha, descendente).
```json
{ "success": true, "simulaciones": [ { "_id": "...", "moneda": "USD", ... } ] }
```

### `DELETE /api/simulaciones/{sim_id}?token=...`
Elimina una simulación **solo si pertenece al usuario** autenticado.
`404` si no existe o no es suya.

---

## Errores comunes

| Código | Descripción |
|---|---|
| `400` | Petición inválida (p. ej. contraseña no cumple la política) |
| `401` | Sesión inválida o expirada / contraseña incorrecta |
| `404` | Recurso no encontrado (usuario, simulación, moneda) |
| `500` | Error interno del servidor |
| `503` | Servicio externo o base de datos no disponible |
