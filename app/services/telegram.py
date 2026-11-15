"""
Cliente de Telegram — envío de mensajes y acciones del bot.

Usa httpx para hacer llamadas directas a la Bot API de Telegram.
"""
import logging

import httpx

from app.config.settings import settings
from app.services.telegram_format import format_model_output, html_to_plain, split_message

logger = logging.getLogger(__name__)

_BASE_URL = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
_TIMEOUT = httpx.Timeout(10.0)


async def _post(method: str, payload: dict) -> httpx.Response:
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        return await client.post(f"{_BASE_URL}/{method}", json=payload)


async def send_message(
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
) -> bool:
    """
    Envía un mensaje HTML. Si Telegram rechaza el HTML (400), reintenta
    el mismo contenido como texto plano para que el mensaje igual llegue.
    """
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_to_message_id:
        payload["reply_parameters"] = {
            "message_id": reply_to_message_id,
            "allow_sending_without_reply": True,
        }

    try:
        response = await _post("sendMessage", payload)
        if response.status_code == 400:
            logger.warning(f"HTML rechazado por Telegram, reenviando como texto: {response.text}")
            payload.pop("parse_mode")
            payload["text"] = html_to_plain(text)
            response = await _post("sendMessage", payload)
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Error HTTP al enviar mensaje a {chat_id}: {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"Error de red al enviar mensaje a {chat_id}: {e}")
    return False


async def send_reply(chat_id: int, model_text: str, reply_to_message_id: int | None = None) -> bool:
    """Envía una respuesta generada por el modelo: la sanitiza y la divide si es larga."""
    ok = True
    for i, chunk in enumerate(split_message(model_text)):
        ok &= await send_message(
            chat_id,
            format_model_output(chunk),
            reply_to_message_id=reply_to_message_id if i == 0 else None,
        )
    return ok


async def send_typing_action(chat_id: int) -> None:
    """Envía la acción "escribiendo..." mientras se genera la respuesta."""
    try:
        await _post("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    except Exception as e:
        logger.debug(f"No se pudo enviar typing action: {e}")


async def set_webhook(webhook_url: str, secret_token: str) -> bool:
    """Registra el webhook en Telegram."""
    payload = {
        "url": webhook_url,
        "secret_token": secret_token,
        "allowed_updates": ["message"],
        "drop_pending_updates": True,
    }
    try:
        response = await _post("setWebhook", payload)
        data = response.json()
        if data.get("ok"):
            logger.info(f"Webhook registrado en: {webhook_url}")
            return True
        logger.error(f"Error al registrar webhook: {data}")
    except Exception as e:
        logger.error(f"Excepción al registrar webhook: {e}")
    return False
