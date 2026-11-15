"""
Orquestador del asistente — punto central de coordinación.

Recibe un mensaje de un socio, coordina memoria, prompt y generación,
y retorna la respuesta final.
"""
import logging

from app.core.memory import get_context_messages, get_or_create_conversation, save_turn
from app.core.prompt_builder import build_prompt
from app.models.socio import Socio
from app.services.gemini import GeminiRateLimitError, generate_response

logger = logging.getLogger(__name__)

_RATE_LIMIT_MESSAGE = (
    "⚠️ Por el momento superamos el límite de consultas a la IA. "
    "Intentá de nuevo en un rato."
)

_ERROR_MESSAGE = (
    "Disculpá, tuve un problema al procesar tu mensaje. "
    "¿Podés intentarlo de nuevo en unos segundos? 🙏"
)


async def process_message(socio: Socio, text: str) -> str:
    """
    Flujo:
    1. Obtener/crear conversación activa
    2. Recuperar historial reciente
    3. Construir prompt (system + historial)
    4. Llamar a Gemini
    5. Persistir el turno
    """
    logger.info(f"Procesando mensaje de socio {socio.telegram_id} ({len(text)} chars)")

    conversacion = await get_or_create_conversation(socio.id)
    mensajes_recientes = await get_context_messages(conversacion)

    system_instruction, contents = build_prompt(
        socio=socio,
        conversacion=conversacion,
        mensajes_recientes=mensajes_recientes,
        pregunta_actual=text,
    )

    try:
        result = await generate_response(contents, system_instruction=system_instruction)
    except GeminiRateLimitError:
        logger.warning(f"Rate limit de Gemini alcanzado para socio {socio.telegram_id}")
        return _RATE_LIMIT_MESSAGE
    except Exception as e:
        logger.error(f"Error al llamar a Gemini: {e}", exc_info=True)
        return _ERROR_MESSAGE

    try:
        await save_turn(
            conversacion=conversacion,
            socio_id=socio.id,
            user_text=text,
            assistant_text=result.text,
            tokens_entrada=result.tokens_entrada,
            tokens_salida=result.tokens_salida,
        )
    except Exception as e:
        # Si falla el guardado, igual retornamos la respuesta al usuario
        logger.error(f"Error al guardar turno en DB: {e}", exc_info=True)

    return result.text
