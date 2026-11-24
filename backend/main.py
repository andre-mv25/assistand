"""API REST de Trading Assistant (FastAPI).

Punto de entrada del backend: inicializa la aplicación, gestiona el ciclo
de vida y la conexión a MongoDB Atlas, configura CORS y middleware, y orquesta
los routers modulares de la API:
- ``routers.auth``: autenticación, tokens y sesiones.
- ``routers.simulaciones``: registro e historial cifrado de simulaciones.
- ``routers.mercado``: cotizaciones Forex, noticias, VADER y tipos de cambio oficiales.
- ``routers.analisis``: pronóstico ARIMA/ARMA y análisis IA con DeepSeek.

También sirve el frontend (SPA HTML/CSS/JS + estáticos).
"""
import os
import threading
import webbrowser
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import connect_db, close_db, is_db_connected, is_db_atlas_connected, reconnect_db
from routers import auth, simulaciones, mercado, analisis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación: conecta la BD al iniciar y la cierra al parar."""
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="Trading Assistant API",
    description="API REST de simulación financiera, análisis de sentimiento y pronóstico estadístico",
    version="1.1.0",
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Manejador global de excepciones: devuelve 500 con el detalle del error."""
    print(f"ERROR en {request.url.path}: {exc}")
    return JSONResponse(content={"error": str(exc)}, status_code=500)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ========== ENDPOINTS DE SISTEMA ==========

@app.get("/", tags=["Sistema"])
async def servir_frontend():
    """Sirve el archivo index.html del frontend."""
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/test", tags=["Sistema"])
async def test_backend():
    """Endpoint de prueba: confirma que la API responde."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/status", tags=["Sistema"])
async def get_status():
    """Estado de la API y de la conexión a la base de datos (Atlas/local)."""
    conectado = is_db_connected()
    if not conectado:
        await reconnect_db()
        conectado = is_db_connected()
    return {
        "api": "online",
        "version": "1.1.0",
        "base_datos": "conectado" if conectado else "desconectado",
        "base_datos_atlas": "conectado" if is_db_atlas_connected() else "desconectado",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/health", tags=["Sistema"])
async def health_check():
    """Health check simple para monitoreo y balanceadores de carga."""
    return {"status": "ok"}


# ========== INCLUSIÓN DE ROUTERS MODULARES ==========
app.include_router(auth.router)
app.include_router(simulaciones.router)
app.include_router(mercado.router)
app.include_router(analisis.router)


# ========== ARCHIVOS ESTÁTICOS ==========
# Servir assets estáticos (CSS, JS, imágenes) - debe ir al final para no
# interceptar las rutas de API definidas arriba.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ========== UTILIDADES DE EJECUCIÓN LOCAL ==========

def abrir_navegador():
    """Abre el navegador en http://localhost:8000 (solo ejecución local)."""
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    import uvicorn
    threading.Timer(2.0, abrir_navegador).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
