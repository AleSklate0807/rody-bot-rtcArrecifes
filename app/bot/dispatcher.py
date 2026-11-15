"""
Dispatcher — enruta los updates de Telegram al handler correcto.
"""
import logging
from typing import Any

from app.bot.handlers import (
    handle_admin,
    handle_help,
    handle_message,
    handle_start,
    handle_unknown,
)

logger = logging.getLogger(__name__)

_ADMIN_COMMANDS = {"/pendientes", "/aprobar", "/bloquear"}


async def dispatch(update: dict[str, Any]) -> None:
    """Punto de entrada para procesar un update de Telegram."""
    message = update.get("message")
    if not message:
        logger.debug(f"Update sin mensaje ignorado: {list(update.keys())}")
        return

    chat = message.get("chat", {})
    if chat.get("type") != "private":
        # Por ahora Rody solo atiende chats privados
        logger.debug(f"Mensaje de chat no privado ignorado: {chat.get('type')}")
        return

    chat_id: int = chat["id"]
    from_user: dict = message.get("from", {})
    telegram_id: int = from_user.get("id", chat_id)
    username: str | None = from_user.get("username")
    first_name: str | None = from_user.get("first_name")
    message_id: int | None = message.get("message_id")

    text: str | None = message.get("text")
    if not text:
        logger.debug(f"Mensaje sin texto ignorado de chat {chat_id}")
        return

    logger.info(f"Dispatching mensaje de telegram_id={telegram_id} ({len(text)} chars)")

    if text.startswith("/"):
        parts = text.split()
        command = parts[0].lower().split("@")[0]  # /start@RodyBot → /start
        args = parts[1:]

        if command == "/start":
            await handle_start(chat_id, telegram_id, username, first_name)
        elif command in ("/ayuda", "/help"):
            await handle_help(chat_id, telegram_id)
        elif command in _ADMIN_COMMANDS:
            await handle_admin(chat_id, telegram_id, command, args)
        else:
            await handle_unknown(chat_id)
        return

    await handle_message(
        chat_id=chat_id,
        telegram_id=telegram_id,
        text=text,
        username=username,
        first_name=first_name,
        message_id=message_id,
    )
