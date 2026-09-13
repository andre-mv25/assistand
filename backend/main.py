"""API REST de Trading Assistant (FastAPI).

Punto de entrada del backend: inicializa la aplicación, gestiona el ciclo
de vida y la conexión a MongoDB, configura CORS y middleware, y orquesta
los routers modulares de la API:
- ``routers.auth``: autenticación, tokens y sesiones.
- ``routers.simulaciones``: registro e historial cifrado de simulaciones.
- ``routers.mercado``: cotizaciones Forex, noticias, VADER y tipos de cambio oficiales.
- ``routers.analisis``: pronóstico ARIMA/ARMA y análisis IA con DeepSeek.

También sirve el frontend (SPA HTML/CSS/JS + estáticos) y levanta el túnel
Cloudflare para pruebas remotas en desarrollo.
"""
import os
import re
import threading
import subprocess
import webbrowser
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from database import connect_db, close_db, is_db_connected, is_db_atlas_connected
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
    version="1.0.0",
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
    return {
        "api": "online",
        "version": "1.0.0",
        "base_datos": "conectado" if is_db_connected() else "desconectado",
        "base_datos_atlas": "conectado" if is_db_atlas_connected() else "desconectado",
        "timestamp": datetime.utcnow().isoformat(),
    }


# ========== INCLUSIÓN DE ROUTERS MODULARES ==========
app.include_router(auth.router)
app.include_router(simulaciones.router)
app.include_router(mercado.router)
app.include_router(analisis.router)


# ========== ARCHIVOS ESTÁTICOS ==========
# Servir assets estáticos (CSS, JS, imágenes) - debe ir al final
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


# ========== UTILIDADES DE EJECUCIÓN LOCAL ==========

def abrir_navegador():
    """Abre el navegador en http://localhost:8000 (solo ejecución local)."""
    webbrowser.open("http://localhost:8000")


CLOUDFLARE_URL = None


def iniciar_cloudflare():
    """Levanta un túnel de Cloudflare (cloudflared) hacia el servidor local.

    Permite acceder al sitio por HTTPS desde cualquier dispositivo mientras se
    ejecuta de forma local. Guarda la URL pública en ``CLOUDFLARE_URL``.
    """
    global CLOUDFLARE_URL
    try:
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", "http://localhost:8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        for line in proc.stdout:
            print(line, end="")
            m = re.search(r"https://[a-zA-Z0-9.-]+\.trycloudflare\.com", line)
            if m:
                CLOUDFLARE_URL = m.group(0)
                print(f"\n{'='*60}")
                print(f"  HTTPS: {CLOUDFLARE_URL}")
                print(f"{'='*60}\n")
                break
    except FileNotFoundError:
        print("[cloudflared] no instalado. Ejecuta: winget install Cloudflare.cloudflared")


if __name__ == "__main__":
    import uvicorn
    threading.Thread(target=iniciar_cloudflare, daemon=True).start()
    threading.Timer(2.0, abrir_navegador).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
