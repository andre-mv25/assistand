from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from datetime import datetime
from pydantic import BaseModel
import os
import asyncio
import webbrowser
import threading
import subprocess
import re
import sys
import hashlib
import secrets
import json

from database import connect_db, close_db, get_db, is_db_connected, is_db_atlas_connected, insert_dual, delete_dual
from security import encrypt_text, decrypt_text, encrypt_num, decrypt_num, hash_key
from services.yfinance_service import obtener_precios_forex, obtener_historico_forex, obtener_precio_par, obtener_historico_par
from services.coingecko_service import obtener_tendencias
from services.deepseek_service import analizar_sentimiento, analizar_semaforo, analizar_historico
from services.news_service import obtener_noticias, obtener_portadas
from services.vader_service import analizar_noticias as analizar_vader
from services.dof_service import obtener_tipo_cambio_dolar
from services.banxico_service import obtener_tipo_cambio, obtener_tipo_cambio_multiples
from services.acciones_service import obtener_acciones


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(title="Trading Assistant API", version="1.0.0", lifespan=lifespan)

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"ERROR en {request.url.path}: {exc}")
    return JSONResponse(content={"error": str(exc)}, status_code=500)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..")


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
        try:
            await insert_dual("prices", {
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


@app.get("/api/par/{from_curr}/{to_curr}")
async def get_par(from_curr: str, to_curr: str):
    par = await obtener_precio_par(from_curr.upper(), to_curr.upper())
    if par is None:
        return {"error": "No se pudo obtener el par"}, 503
    return par


@app.get("/api/historico_par/{from_curr}/{to_curr}")
async def get_historico_par(from_curr: str, to_curr: str, dias: int = Query(60)):
    historico = await obtener_historico_par(from_curr.upper(), to_curr.upper(), dias)
    if historico is None:
        return {"error": f"No se pudo obtener historico para {from_curr}/{to_curr}"}, 503
    return {
        "from": from_curr.upper(),
        "to": to_curr.upper(),
        "datos": historico,
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
            await insert_dual("analisis", {
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


@app.post("/api/analizar_historico")
async def post_analizar_historico(data: dict = Body(...)):
    moneda = data.get("moneda", "USD").upper()
    precios = data.get("precios", [])
    capital_inicial = data.get("capital_inicial", 0)
    capital_final = data.get("capital_final", 0)
    rendimiento = data.get("rendimiento", 0)
    sharpe = data.get("sharpe", 0)
    drawdown = data.get("drawdown", 0)
    win_rate = data.get("win_rate", 0)

    vader = data.get("vader")

    if not precios:
        return {"error": "No hay datos historicos"}, 400

    tipos_cambio = None
    try:
        precios_fx = await obtener_precios_forex()
        if precios_fx:
            tasas = {}
            for a in ["USD", "EUR", "JPY"]:
                for b in ["MXN"]:
                    pa = precios_fx.get(a, {}).get("precio")
                    pb = precios_fx.get(b, {}).get("precio")
                    if pa and pb:
                        tasas[f"{a}/{b}"] = round(pa / pb, 6)
            for a, b in [("EUR", "USD"), ("USD", "JPY"), ("EUR", "JPY")]:
                pa = precios_fx.get(a, {}).get("precio")
                pb = precios_fx.get(b, {}).get("precio")
                if pa and pb:
                    tasas[f"{a}/{b}"] = round(pa / pb, 6)
            tipos_cambio = tasas
    except Exception as e:
        print(f"Error obteniendo tipos de cambio: {e}")

    acciones = None
    try:
        acciones = await obtener_acciones()
        if acciones:
            acciones = acciones[:220]
    except Exception as e:
        print(f"Error obteniendo acciones: {e}")

    analisis = await analizar_historico(moneda, precios, capital_inicial, capital_final, rendimiento, sharpe, drawdown, win_rate, vader, tipos_cambio, acciones)
    if analisis is None:
        return {"error": "No se pudo obtener analisis de DeepSeek"}, 503

    db = get_db()
    if db is not None:
        try:
            await insert_dual("analisis_historico", {
                "moneda": moneda,
                "precios_muestra": precios[:5],
                "total_datos": len(precios),
                "rendimiento": rendimiento,
                "sharpe": sharpe,
                "drawdown": drawdown,
                "win_rate": win_rate,
                "vader_enc": encrypt_text(json.dumps(vader)) if vader else None,
                "analisis_deepseek_enc": encrypt_text(json.dumps(analisis)),
                "timestamp": datetime.utcnow(),
            })
        except Exception as e:
            print(f"Error DB insert analisis_historico: {e}")

    return {
        "moneda": moneda,
        "analisis": analisis,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/api/status")
async def get_status():
    return {
        "api": "online",
        "version": "1.0.0",
        "base_datos": "conectado" if is_db_connected() else "desconectado",
        "base_datos_atlas": "conectado" if is_db_atlas_connected() else "desconectado",
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


@app.get("/api/vader")
async def get_vader(query: str = Query("forex OR trading OR divisas"), cantidad: int = Query(2000, ge=1, le=2000)):
    resultado = await analizar_vader(query=query, cantidad=cantidad)
    if resultado is None:
        return {"error": "No se pudieron analizar noticias con VADER"}, 503
    return resultado


@app.get("/api/dof/tipo_cambio")
async def get_dof_tipo_cambio():
    resultado = await obtener_tipo_cambio_dolar()
    if resultado is None:
        return {"error": "No se pudo obtener el tipo de cambio del DOF"}, 503
    return resultado


@app.get("/api/banxico/tipo_cambio")
async def get_banxico_tipo_cambio(moneda: str = Query("USD")):
    resultado = await obtener_tipo_cambio(moneda)
    if resultado is None:
        return {"error": f"No se pudo obtener el tipo de cambio de {moneda} en Banxico"}, 503
    return resultado


@app.get("/api/banxico/tipo_cambio_all")
async def get_banxico_tipo_cambio_all():
    resultado = await obtener_tipo_cambio_multiples()
    if resultado is None:
        return {"error": "No se pudieron obtener los tipos de cambio de Banxico"}, 503
    return resultado


# ========== AUTENTICACIÓN ==========

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class SimulacionRequest(BaseModel):
    token: str
    moneda: str = ""
    monto: float = 0
    capital_inicial: float = 0
    capital_final: float = 0
    rendimiento: float = 0
    sharpe: float = 0
    drawdown: float = 0
    win_rate: float = 0
    generado: float = 0
    compound: float = 0
    sentimiento: str = ""
    recomendacion: str = ""
    confianza: float = 0
    analisis: str = ""


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except (ValueError, AttributeError):
        return False


def generar_token() -> str:
    return secrets.token_hex(32)


async def crear_sesion(username: str) -> str:
    token = generar_token()
    db = get_db()
    if db is not None:
        try:
            from datetime import timedelta
            await insert_dual("sessions", {
                "token_hash": hash_key(token),
                "username_hash": hash_key(username),
                "username_enc": encrypt_text(username),
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=30),
            })
        except Exception as e:
            print(f"Error creando sesion: {e}")
    return token


async def validar_token(token: str):
    if not token:
        return None
    db = get_db()
    if db is None:
        return None
    try:
        from datetime import datetime as dt
        sesion = await db.sessions.find_one({
            "token_hash": hash_key(token),
            "expires_at": {"$gt": dt.utcnow()},
        })
        if sesion:
            sesion["username"] = decrypt_text(sesion.get("username_enc"))
        return sesion
    except Exception:
        return None


@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)

    if len(req.username.strip()) < 3:
        return JSONResponse(content={"error": "El usuario debe tener al menos 3 caracteres"}, status_code=400)
    if len(req.password.strip()) < 4:
        return JSONResponse(content={"error": "La contraseña debe tener al menos 4 caracteres"}, status_code=400)

    existing = await db.users.find_one({"username_hash": hash_key(req.username.strip())})
    if existing:
        return JSONResponse(content={"error": "El nombre de usuario ya existe"}, status_code=400)

    hashed = hash_password(req.password.strip())
    email = req.email.strip()
    await insert_dual("users", {
        "username_hash": hash_key(req.username.strip()),
        "username_enc": encrypt_text(req.username.strip()),
        "password": hashed,
        "email_enc": encrypt_text(email) if email else None,
        "created_at": datetime.utcnow(),
    })
    token = await crear_sesion(req.username.strip())
    return {"success": True, "message": "Cuenta creada exitosamente", "token": token, "username": req.username.strip()}


@app.post("/api/auth/login")
async def login(req: LoginRequest):
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)

    user = await db.users.find_one({"username_hash": hash_key(req.username.strip())})
    if not user:
        return JSONResponse(content={"error": "El usuario no existe"}, status_code=404)

    if not verify_password(req.password.strip(), user["password"]):
        return JSONResponse(content={"error": "Contraseña incorrecta"}, status_code=401)

    token = await crear_sesion(req.username.strip())
    return {"success": True, "message": "Inicio de sesión exitoso", "token": token, "username": req.username.strip()}


@app.get("/api/auth/me")
async def auth_me(token: str = Query("")):
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    return {"success": True, "username": sesion["username"]}


@app.post("/api/auth/logout")
async def logout(token: str = Query("")):
    db = get_db()
    if db is not None and token:
        try:
            await delete_dual("sessions", {"token_hash": hash_key(token)})
        except Exception:
            pass
    return {"success": True}


# ========== HISTORIAL DE SIMULACIONES POR USUARIO ==========

from bson import ObjectId

SIMULACION_CAMPOS_TEXTO = ["moneda", "sentimiento", "recomendacion", "analisis"]
SIMULACION_CAMPOS_NUMERO = [
    "monto", "capital_inicial", "capital_final", "rendimiento", "sharpe",
    "drawdown", "win_rate", "generado", "compound", "confianza",
]


@app.post("/api/simulaciones")
async def guardar_simulacion(req: SimulacionRequest):
    sesion = await validar_token(req.token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)
    try:
        doc = req.model_dump(exclude={"token"})
        doc["username_hash"] = hash_key(sesion["username"])
        doc["username_enc"] = encrypt_text(sesion["username"])
        doc["fecha"] = datetime.utcnow()
        for campo in SIMULACION_CAMPOS_TEXTO:
            v = doc.get(campo)
            if v is not None:
                doc[campo] = encrypt_text(v)
        for campo in SIMULACION_CAMPOS_NUMERO:
            v = doc.get(campo)
            if v is not None:
                doc[campo] = encrypt_num(v)
        res = await insert_dual("simulaciones", doc)
        return {"success": True, "id": str(res)}
    except Exception as e:
        print(f"Error guardando simulacion: {e}")
        return JSONResponse(content={"error": "No se pudo guardar la simulacion"}, status_code=500)


@app.get("/api/simulaciones")
async def listar_simulaciones(token: str = Query("")):
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)
    try:
        cursor = db.simulaciones.find({"username_hash": hash_key(sesion["username"])}).sort("fecha", -1).limit(50)
        simulaciones = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["username"] = decrypt_text(doc.get("username_enc"))
            for campo in SIMULACION_CAMPOS_TEXTO:
                doc[campo] = decrypt_text(doc.get(campo))
            for campo in SIMULACION_CAMPOS_NUMERO:
                doc[campo] = decrypt_num(doc.get(campo))
            simulaciones.append(doc)
        return {"success": True, "simulaciones": simulaciones}
    except Exception as e:
        print(f"Error listando simulaciones: {e}")
        return JSONResponse(content={"error": "No se pudo listar el historial"}, status_code=500)


@app.delete("/api/simulaciones/{sim_id}")
async def eliminar_simulacion(sim_id: str, token: str = Query("")):
    sesion = await validar_token(token)
    if not sesion:
        return JSONResponse(content={"error": "Sesión inválida o expirada"}, status_code=401)
    db = get_db()
    if db is None:
        return JSONResponse(content={"error": "Base de datos no disponible"}, status_code=503)
    try:
        res = await delete_dual("simulaciones", {"_id": ObjectId(sim_id), "username_hash": hash_key(sesion["username"])})
        if res == 0:
            return JSONResponse(content={"error": "Simulacion no encontrada"}, status_code=404)
        return {"success": True}
    except Exception as e:
        print(f"Error eliminando simulacion: {e}")
        return JSONResponse(content={"error": "No se pudo eliminar la simulacion"}, status_code=500)


# Servir assets estáticos (CSS, JS, imágenes)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def abrir_navegador():
    webbrowser.open("http://localhost:8000")


CLOUDFLARE_URL = None


def iniciar_cloudflare():
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
