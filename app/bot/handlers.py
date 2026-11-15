"""
Handlers de mensajes de Telegram.

Cada handler coordina la respuesta, separando la comunicación (Telegram)
del núcleo del asistente.
"""
import html
import logging

from app.config.settings import settings
from app.core.assistant import process_message
from app.core.prompt_builder import TEMAS, build_welcome_message
from app.models.socio import Socio
from app.services.supabase_client import (
    get_or_create_socio,
    list_pending_socios,
    set_socio_activo,
)
from app.services.telegram import send_message, send_reply, send_typing_action

logger = logging.getLogger(__name__)


async def _identify(
    chat_id: int,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
) -> Socio | None:
    """
    Registra o recupera al socio. Si no está habilitado, le avisa (y a los
    admins, si es nuevo) y retorna None.
    """
    nombre_display = first_name or (f"@{username}" if username else None)
    try:
        socio, creado = await get_or_create_socio(
            telegram_id=telegram_id, username=username, nombre_display=nombre_display
        )
    except Exception as e:
        logger.error(f"Error al registrar socio {telegram_id}: {e}", exc_info=True)
        await send_message(chat_id, "Tuve un problema al identificarte. Intentá de nuevo en unos segundos.")
        return None

    if socio.activo:
        return socio

    await send_message(
        chat_id,
        "🦊 ¡Hola! Soy <b>Rody</b>, el zorrito piloto y mascota de Rotaract Club Arrecifes.\n\n"
        "Tu acceso todavía no fue aprobado. Ya le avisé a la gente del club; "
        "en cuanto te habiliten vas a poder usarme.\n\n"
        f"Tu ID de Telegram es <code>{telegram_id}</code>.",
    )
    if creado:
        await _notify_admins(
            "🆕 <b>Nuevo pedido de acceso</b>\n"
            f"{html.escape(socio.nombre)} (<code>{telegram_id}</code>)\n\n"
            f"Para habilitarlo: <code>/aprobar {telegram_id}</code>"
        )
    return None


async def _notify_admins(text: str) -> None:
    for admin_id in settings.admin_ids:
        await send_message(admin_id, text)


async def handle_message(
    chat_id: int,
    telegram_id: int,
    text: str,
    username: str | None = None,
    first_name: str | None = None,
    message_id: int | None = None,
) -> None:
    """Procesa un mensaje de texto y envía la respuesta del asistente."""
    socio = await _identify(chat_id, telegram_id, username, first_name)
    if socio is None:
        return

    await send_typing_action(chat_id)

    try:
        respuesta = await process_message(socio=socio, text=text)
    except Exception as e:
        logger.error(f"Error inesperado al procesar mensaje: {e}", exc_info=True)
        respuesta = "Disculpá, algo salió mal. ¿Podés intentarlo de nuevo?"

    await send_reply(chat_id, respuesta, reply_to_message_id=message_id)


async def handle_start(
    chat_id: int,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> None:
    """Comando /start: registra al socio y envía la bienvenida."""
    socio = await _identify(chat_id, telegram_id, username, first_name)
    if socio is None:
        return
    await send_message(chat_id, build_welcome_message(socio))


async def handle_help(chat_id: int, telegram_id: int) -> None:
    """Comando /ayuda."""
    help_text = (
        "🦊 <b>Rody — la mascota de Rotaract Club Arrecifes</b>\n\n"
        "<b>Podés preguntarme sobre:</b>\n"
        f"{TEMAS}\n"
        "<b>Comandos disponibles:</b>\n"
        "/start — Reiniciar el asistente\n"
        "/ayuda — Ver este mensaje\n"
    )
    if telegram_id in settings.admin_ids:
        help_text += (
            "\n<b>Comandos de admin:</b>\n"
            "/pendientes — Ver pedidos de acceso\n"
            "/aprobar &lt;id&gt; — Habilitar a un socio\n"
            "/bloquear &lt;id&gt; — Deshabilitar a un socio\n"
        )
    help_text += "\nEscribime cualquier pregunta directamente, ¡sin formalidades! 😊"
    await send_message(chat_id, help_text)


async def handle_admin(chat_id: int, telegram_id: int, command: str, args: list[str]) -> None:
    """Comandos de administración: /pendientes, /aprobar, /bloquear."""
    if telegram_id not in settings.admin_ids:
        await handle_unknown(chat_id)
        return

    if command == "/pendientes":
        pendientes = await list_pending_socios()
        if not pendientes:
            await send_message(chat_id, "No hay pedidos de acceso pendientes ✅")
            return
        lineas = [
            f"- {html.escape(s.nombre)} — <code>/aprobar {s.telegram_id}</code>" for s in pendientes
        ]
        await send_message(chat_id, "<b>Pedidos pendientes:</b>\n" + "\n".join(lineas))
        return

    if not args or not args[0].lstrip("-").isdigit():
        await send_message(chat_id, f"Uso: <code>{command} &lt;telegram_id&gt;</code>")
        return

    target_id = int(args[0])
    activo = command == "/aprobar"
    socio = await set_socio_activo(target_id, activo)
    if socio is None:
        await send_message(chat_id, f"No encontré ningún socio con ID <code>{target_id}</code>.")
        return

    estado = "habilitado ✅" if activo else "deshabilitado ⛔"
    await send_message(chat_id, f"{html.escape(socio.nombre)} quedó {estado}.")
    if activo:
        await send_message(
            target_id,
            "🎉 ¡Listo! Ya tenés acceso a <b>Rody</b>. Escribime lo que necesites o usá /ayuda.",
        )


async def handle_unknown(chat_id: int) -> None:
    """Responde a comandos desconocidos."""
    await send_message(chat_id, "No reconozco ese comando. Usá /ayuda para ver qué puedo hacer por vos.")
