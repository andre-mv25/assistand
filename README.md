# Trading Assistant

Plataforma web de análisis financiero para simular inversiones en **divisas** y **acciones** con dinero virtual y datos reales del mercado, orientada a la **educación práctica del inversionista principiante**.

**Proyecto de tesis** — Universidad Tres Culturas
**Autores:** Martínez Jurado Diego Alberto · Miranda Vargas Andre · Vázquez Morales Luis Osvaldo

---

## Descripción

Trading Assistant permite aprender a invertir **sin arriesgar capital real**:

- Simulación de inversiones en divisas (USD, MXN, JPY, EUR) y acciones con datos reales de Yahoo Finance.
- Estrategia automatizada **SMA crossover (SMA5/SMA20)** con stop-loss.
- Análisis de **sentimiento** de noticias con VADER (NewsAPI + Google News + GNews).
- **Veredicto de IA** con DeepSeek en español: explica qué hacer y por qué.
- **Pronóstico estadístico** ARIMA/ARMA: proyección a 5 días con bandas de confianza y señal de compra/venta/neutral.
- **Semáforo combinado**: 60% noticias/IA + 40% estadística, con regla de consistencia ("con reserva" si se contradicen).
- Métricas de rendimiento: rendimiento, Sharpe, drawdown y win rate.
- Historial por usuario con **cifrado selectivo** (Fernet) en MongoDB Atlas.

URL de producción: https://assistand.onrender.com

---

## Arquitectura

```
┌─────────────┐      HTTP/JSON       ┌──────────────┐      MongoDB ──────────┐
│  Frontend   │ ───────────────────► │   Backend    │ ◄── Atlas + local ────┤
│  (SPA HTML/ │   fetch()/API REST   │  FastAPI +   │                       │
│  CSS/JS +   │ ◄─────────────────── │  Python 3.13 │                       │
│  Chart.js)  │                      └──────┬───────┘                       │
└─────────────┘                             │
                                     Servicios externos:
                     Yahoo Finance · Banxico · DOF · NewsAPI · GNews · DeepSeek · CoinGecko
```

- **Frontend:** `index.html` (SPA en español) + `assets/css/trading.css` + Chart.js.
- **Backend:** API REST con FastAPI (async) en `backend/`, base de datos MongoDB con Motor.
- **Despliegue:** Render (producción) con MongoDB Atlas; respaldo local en desarrollo.

---

## Estructura del proyecto

```
html5up-dimension/
├── index.html                 # Frontend SPA (todo el JS de la interfaz)
├── assets/
│   ├── css/
│   │   ├── main.css           # Plantilla base (html5up Dimension)
│   │   └── trading.css        # Estilos propios de Trading Assistant
│   └── images/
├── backend/
│   ├── main.py                # API FastAPI: endpoints + lógica de negocio
│   ├── database.py            # Conexión a MongoDB (Atlas con respaldo local)
│   ├── security.py            # Cifrado Fernet y hashes (SHA-256)
│   ├── config.py              # Variables de entorno y claves de API
│   └── services/
│       ├── yfinance_service.py     # Cotizaciones e históricos Forex/acciones
│       ├── arima_service.py        # Pronóstico ARIMA y señal ARMA (numpy puro)
│       ├── deepseek_service.py     # IA: sentimiento, semáforo y veredicto final
│       ├── vader_service.py        # Análisis de sentimiento con VADER
│       ├── news_service.py         # Noticias vía NewsAPI
│       ├── google_news_service.py  # Noticias vía Google News RSS
│       ├── gnews_service.py        # Noticias vía GNews API
│       ├── banxico_service.py      # Tipo de cambio oficial FIX (Banxico)
│       ├── dof_service.py          # Tipo de cambio del DOF
│       ├── coingecko_service.py    # Cripto: sentimiento y tendencias
│       ├── forex_service.py        # Alternativa de precios vía Frankfurter
│       └── acciones_service.py     # Ranking de acciones con RSI/momentum
└── requirements.txt           # Dependencias de Python
```

---

## Requisitos

- Python 3.11+
- MongoDB local (opcional; en producción se usa Atlas)
- Node.js (solo para verificar sintaxis del JS de forma local)

### Variables de entorno (`backend/.env`)

| Variable | Descripción |
|---|---|
| `MONGO_URI_ATLAS` | Cadena de conexión a MongoDB Atlas (nube) |
| `MONGO_URI_LOCAL` | Cadena de conexión a MongoDB local (default `mongodb://localhost:27017`) |
| `MONGO_DB` | Nombre de la base de datos (default `trading_assistant`) |
| `DEEPSEEK_API_KEY` | Clave de la API de DeepSeek |
| `NEWS_API_KEY` | Clave de NewsAPI |
| `GNEWS_API_KEY` | Clave de GNews |
| `BANXICO_API_KEY` | Clave de la API de Banxico |
| `ENCRYPTION_KEY` | Clave Fernet para cifrado de datos sensibles |
| `INTERVALO_ACTUALIZACION` | Intervalo de refresco de datos (segundos) |

---

## Ejecución local

```bash
# 1. Crear y activar el entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
source .venv/bin/activate     # Linux/macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear backend/.env con las claves (ver tabla anterior)

# 4. Levantar la API (sirve también el frontend)
cd backend
python main.py
# → http://localhost:8000
```

Al iniciar, la app abre el navegador automáticamente y (si está instalado
`cloudflared`) levanta un túnel HTTPS para probar desde el celular.

---

## Base de datos (MongoDB)

Colecciones principales:

| Colección | Descripción |
|---|---|
| `users` | Usuarios: `username_hash`, `username`, `password` (hash SHA-256 + salt), `created_at` |
| `sessions` | Sesiones: `token_hash`, `username_hash`, `created_at`, `expires_at` (30 días) |
| `simulaciones` | Resultados de simulación por usuario (campos sensibles cifrados con Fernet) |
| `analisis_historico` | Análisis IA de cada simulación (VADER + DeepSeek, cifrados) |
| `analisis` | Log del semáforo por moneda |
| `prices` | Historial de cotizaciones |

Ver el diagrama ER: `docs/` (imágenes generadas para la tesis).

---

## Documentación de la API

Toda la API REST está documentada en **`docs/API.md`**, y también disponible de
forma interactiva en `http://localhost:8000/docs` (Swagger UI de FastAPI).

---

## Seguridad

- Contraseñas con **hash SHA-256 + salt aleatorio** (nunca en texto plano).
- Tokens de sesión aleatorios (64 hex) con **caducidad de 30 días**; en BD solo su hash.
- **Cifrado selectivo Fernet** (AES-128-CBC) para montos, rendimientos, análisis y recomendaciones; `username` y fechas quedan en texto plano para poder consultarlos.
- Registro con **política de contraseña fuerte**: mínimo 8 caracteres, al menos una mayúscula, un número y un carácter especial.

---

## Tecnologías

- **Backend:** Python · FastAPI · Motor (MongoDB async)
- **Frontend:** HTML · CSS · JavaScript · Chart.js
- **Datos:** yfinance (Yahoo Finance) · Frankfurter · Banxico · DOF · NewsAPI · GNews · CoinGecko
- **IA:** DeepSeek API · VADER (análisis de sentimiento)
- **Estadística:** ARIMA/ARMA (numpy puro)
- **Nube:** Render · MongoDB Atlas · Cloudflare (túnel de desarrollo)
