from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
import os
import webbrowser
import threading

from database import connect_db, close_db, get_db
from services.yfinance_service import obtener_precios_forex, obtener_historico_forex
from services.coingecko_service import obtener_tendencias
from services.deepseek_service import analizar_sentimiento, analizar_semaforo
from services.news_service import obtener_noticias, obtener_portadas


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(title="Trading Assistant API", version="1.0.0", lifespan=lifespan)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"ERROR en {request.url.path}: {exc}")
    return {"error": str(exc)}, 500

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.get("/")
async def servir_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/api/test")
async def test_backend():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/precios")
async def get_precios():
    monedas = await obtener_precios_forex()
    if monedas is None:
        return {"error": "No se pudieron obtener precios Forex"}, 503
    db = get_db()
    if db is not None:
        for moneda, data in monedas.items():
            try:
                await db.prices.insert_one({
                    "moneda": moneda,
                    "precio": data["precio"],
                    "cambio": data["cambio"],
                    "timestamp": datetime.utcnow(),
                })
            except Exception as e:
                print(f"Error DB insert: {e}")
    return {
        "monedas": monedas,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/precios/{moneda}")
async def get_precio_moneda(moneda: str):
    monedas = await obtener_precios_forex()
    if monedas is None:
        return {"error": "No se pudieron obtener precios Forex"}, 503
    data = monedas.get(moneda.upper())
    if not data:
        return {"error": f"Moneda {moneda} no soportada"}, 404
    return {
        "moneda": moneda.upper(),
        "precio": data["precio"],
        "cambio": data["cambio"],
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/analisis")
async def get_analisis(moneda: str = Query("USD")):
    moneda = moneda.upper()
    monedas = await obtener_precios_forex()
    if monedas is None:
        return {"error": "No se pudieron obtener precios Forex"}, 503
    data = monedas.get(moneda)
    if not data:
        return {"error": f"Moneda {moneda} no soportada"}, 404

    analisis = await analizar_sentimiento(moneda, data["precio"], data["cambio"])

    query = f"{moneda} forex OR {moneda} trading OR {moneda} currency"
    noticias = await obtener_noticias(query=query, cantidad=10)
    semaforo = await analizar_semaforo(moneda, noticias) if noticias else None

    db = get_db()
    if db is not None:
        try:
            await db.analisis.insert_one({
                "moneda": moneda,
                "precio": data["precio"],
                "cambio": data["cambio"],
                "analisis_deepseek": analisis,
                "semaforo": semaforo,
                "timestamp": datetime.utcnow(),
            })
        except Exception as e:
            print(f"Error DB insert analisis: {e}")

    return {
        "moneda": moneda,
        "precio": data["precio"],
        "cambio": data["cambio"],
        "analisis_deepseek": analisis,
        "semaforo": semaforo,
        "noticias_analizadas": len(noticias) if noticias else 0,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/metricas")
async def get_metricas(moneda: str = Query("USD")):
    import random
    rendimiento = round(random.uniform(-5, 15), 1)
    sharpe = round(random.uniform(0.5, 3.0), 2)
    drawdown = round(random.uniform(1, 12), 1)
    win_rate = round(random.uniform(40, 85), 0)

    return {
        "moneda": moneda.upper(),
        "rendimiento": rendimiento,
        "sharpe": sharpe,
        "drawdown": drawdown,
        "win_rate": win_rate,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/tendencias")
async def get_tendencias():
    tendencias = await obtener_tendencias()
    if tendencias is None:
        return {"error": "No se pudieron obtener tendencias"}, 503
    return {
        "tendencias": tendencias,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/historico/{moneda}")
async def get_historico(moneda: str, dias: int = Query(30)):
    historico = await obtener_historico_forex(moneda.upper(), dias)
    if historico is None:
        return {"error": f"No se pudo obtener historico para {moneda.upper()}"}, 503
    return {
        "moneda": moneda.upper(),
        "datos": historico,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/status")
async def get_status():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "conectado"
    except:
        db_status = "desconectado"

    return {
        "api": "online",
        "version": "1.0.0",
        "base_datos": db_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/noticias")
async def get_noticias(
    query: str = Query("forex OR trading OR divisas"),
    fuentes: str = Query(None),
    cantidad: int = Query(10, ge=1, le=50),
):
    lista_fuentes = fuentes.split(",") if fuentes else None
    noticias = await obtener_noticias(query, lista_fuentes, cantidad)
    if noticias is None:
        return {"error": "No se pudieron obtener noticias"}, 503
    return {
        "noticias": noticias,
        "total": len(noticias),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/noticias/portadas")
async def get_portadas(
    categoria: str = Query("business"),
    pais: str = Query("us"),
    cantidad: int = Query(5, ge=1, le=20),
):
    noticias = await obtener_portadas(categoria, pais, cantidad)
    if noticias is None:
        return {"error": "No se pudieron obtener portadas"}, 503
    return {
        "noticias": noticias,
        "total": len(noticias),
        "timestamp": datetime.utcnow().isoformat(),
    }


# Servir assets estáticos (CSS, JS, imágenes)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def abrir_navegador():
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    import uvicorn
    threading.Timer(1.5, abrir_navegador).start()
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
