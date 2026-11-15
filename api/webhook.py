"""
Vercel Serverless Function — Entry point del webhook de Telegram.

Este archivo es el único punto de entrada para Vercel.
Recibe los updates de Telegram via POST /api/webhook y los procesa.

Rutas:
  POST /api/webhook → Procesa update de Telegram
  GET  /api/webhook → Health check (para pings de monitoreo)
  GET  /health      → Alias del health check (configurado en vercel.json)
"""
import sys
import os
import logging

# Asegurar que el directorio raíz del proyecto esté en el path de Python.
# Necesario para que Vercel pueda importar los módulos de 'app/'.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.bot.dispatcher import dispatch
from app.services.supabase_client import is_update_processed, mark_update_processed

# ---- Configuración de logging ----
logging.basicConfig(
    level=settings.log_level_int,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---- Aplicación FastAPI ----
# Vercel detecta automáticamente la variable 'app' como la ASGI app a servir.
app = FastAPI(
    title="Rody Bot",
    description="Asistente virtual de Rotaract Club Arrecifes",
    version="1.0.0",
    docs_url=None,  # Deshabilitar Swagger en producción
    redoc_url=None,
)


@app.post("/api/webhook")
async def webhook(request: Request) -> JSONResponse:
    """
    Recibe y procesa un update de Telegram.

    Telegram envía un POST con el JSON del update cada vez que
    un usuario le escribe al bot.

    Siempre retorna 200 OK para evitar que Telegram reintente el envío.
    La validación del secret header previene requests no autorizados.
    """
    # 1. Validar el secret token (previene requests falsificados)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        logger.warning(
            f"Request rechazado: secret inválido desde {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(status_code=403, detail="Forbidden")

    # 2. Parsear el update
    try:
        update = await request.json()
    except Exception as e:
        logger.error(f"Error al parsear JSON del update: {e}")
        return JSONResponse(content={"ok": True})  # Siempre 200 para Telegram

    update_id: int = update.get("update_id", 0)
    logger.info(f"Update recibido: update_id={update_id}")

    # 3. Idempotencia: ignorar updates ya procesados
    if update_id and await is_update_processed(update_id):
        logger.info(f"Update {update_id} ya procesado, ignorando.")
        return JSONResponse(content={"ok": True})

    # 4. Marcar como procesado ANTES de procesar (evita duplicados por retry)
    if update_id:
        await mark_update_processed(update_id)

    # 5. Procesar el update (despachar al handler correcto)
    try:
        await dispatch(update)
    except Exception as e:
        # Capturar cualquier excepción no manejada para no perder el 200 OK
        logger.error(f"Error no manejado al despachar update {update_id}: {e}", exc_info=True)

    # Siempre retornar 200 OK a Telegram
    return JSONResponse(content={"ok": True})


@app.get("/api/webhook")
@app.get("/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint.

    Usado por:
    - Verificación de despliegue en Vercel
    - Monitoreo externo (si se configura)
    - Validar que el bot está activo
    """
    return JSONResponse(
        content={
            "status": "ok",
            "bot": "Rody",
            "club": "Rotaract Club Arrecifes",
            "version": "1.0.0",
            "environment": settings.BOT_ENVIRONMENT,
        }
    )

