"""
Gestión de memoria conversacional.

Cada socio tiene una conversación activa. Cuando llega a
SUMMARY_TRIGGER_TURNS turnos, se resume (integrando el resumen anterior),
se cierra y se abre una nueva que arranca con ese resumen como contexto.
Así el prompt siempre lleva: resumen acumulado + últimos turnos, sin
superposición y sin regenerar el resumen en cada mensaje.
"""
import logging
from typing import Optional
from uuid import UUID

from app.config.settings import settings
from app.models.conversacion import Conversacion, Mensaje
from app.services.supabase_client import (
    close_conversation,
    create_conversation,
    get_active_conversation,
    get_recent_messages,
    save_message,
    update_conversation,
)
from app.services.gemini import generate_summary

logger = logging.getLogger(__name__)


async def get_or_create_conversation(socio_id: UUID) -> Conversacion:
    """Retorna la conversación activa del socio, o crea una nueva si no existe."""
    conversacion = await get_active_conversation(socio_id)
    if conversacion is None:
        conversacion = await create_conversation(socio_id)
    return conversacion


async def get_context_messages(conversacion: Conversacion) -> list[Mensaje]:
    """Últimos turnos de la conversación activa (cada turno = user + assistant)."""
    return await get_recent_messages(conversacion.id, limit=settings.MAX_RECENT_TURNS * 2)


async def save_turn(
    conversacion: Conversacion,
    socio_id: UUID,
    user_text: str,
    assistant_text: str,
    tokens_entrada: Optional[int] = None,
    tokens_salida: Optional[int] = None,
) -> None:
    """Guarda el turno completo y actualiza contadores; rota la conversación si corresponde."""
    await save_message(conversacion.id, socio_id, "user", user_text, tokens_entrada=tokens_entrada)
    await save_message(conversacion.id, socio_id, "assistant", assistant_text, tokens_salida=tokens_salida)

    total_turnos = conversacion.total_turnos + 1
    await update_conversation(
        conversacion_id=conversacion.id,
        total_turnos=total_turnos,
        tokens_usados=conversacion.tokens_usados + (tokens_entrada or 0) + (tokens_salida or 0),
    )

    if total_turnos >= settings.SUMMARY_TRIGGER_TURNS:
        await _rotate_conversation(conversacion, socio_id)


async def _rotate_conversation(conversacion: Conversacion, socio_id: UUID) -> None:
    """Resume la conversación, la cierra y abre una nueva con el resumen."""
    logger.info(f"Rotando conversación {conversacion.id}")
    mensajes = await get_recent_messages(conversacion.id, limit=settings.SUMMARY_TRIGGER_TURNS * 2)
    conversation_text = "\n".join(
        f"{'Socio' if m.rol == 'user' else 'Rody'}: {m.contenido}" for m in mensajes
    )

    try:
        resumen = await generate_summary(conversation_text, resumen_previo=conversacion.resumen)
    except Exception as e:
        # Si falla el resumen, se reintentará en el próximo turno
        logger.error(f"Error al resumir conversación {conversacion.id}: {e}")
        return

    await update_conversation(conversacion_id=conversacion.id, resumen=resumen)
    await close_conversation(conversacion.id)
    await create_conversation(socio_id, resumen=resumen)
