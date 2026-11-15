"""
Cliente de Gemini — generación de respuestas.

Usa el SDK oficial `google-genai` con reintentos automáticos ante
rate limiting (429) y errores transitorios del servidor (5xx).
"""
import logging
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import errors, types
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config.settings import settings

logger = logging.getLogger(__name__)

_client = genai.Client(api_key=settings.GEMINI_API_KEY)


class GeminiRateLimitError(Exception):
    """Se superó la cuota de la API de Gemini (HTTP 429)."""


@dataclass
class GeminiResult:
    text: str
    tokens_entrada: Optional[int] = None
    tokens_salida: Optional[int] = None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, errors.ServerError):
        return True
    return isinstance(exc, errors.ClientError) and exc.code == 429


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def _generate(
    contents: str | list[types.Content],
    system_instruction: Optional[str],
    temperature: float,
) -> types.GenerateContentResponse:
    return await _client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=2048,
        ),
    )


async def generate_response(
    contents: str | list[types.Content],
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
) -> GeminiResult:
    """
    Genera una respuesta con Gemini.

    Raises:
        GeminiRateLimitError: si se agotó la cuota tras los reintentos.
        errors.APIError: para otros errores de la API.
    """
    try:
        response = await _generate(contents, system_instruction, temperature)
    except errors.ClientError as e:
        if e.code == 429:
            raise GeminiRateLimitError(str(e)) from e
        raise

    text = (response.text or "").strip()
    if not text:
        logger.warning("Gemini retornó una respuesta vacía")
        text = "Disculpá, no pude generar una respuesta. Intentá de nuevo."

    usage = response.usage_metadata
    return GeminiResult(
        text=text,
        tokens_entrada=usage.prompt_token_count if usage else None,
        tokens_salida=usage.candidates_token_count if usage else None,
    )


async def generate_summary(conversation_text: str, resumen_previo: Optional[str] = None) -> str:
    """Genera un resumen comprimido de una conversación larga."""
    previo = (
        f"RESUMEN DE LO CONVERSADO ANTES:\n{resumen_previo}\n\n" if resumen_previo else ""
    )
    prompt = (
        "Resumí la siguiente conversación entre un socio de Rotaract Club Arrecifes "
        "y el asistente virtual Rody, en no más de 3 párrafos. Capturá los temas "
        "principales, lo que pidió el socio y las respuestas clave. Si hay un resumen "
        "previo, integralo. Escribí en tercera persona, en español y en texto plano.\n\n"
        f"{previo}CONVERSACIÓN:\n{conversation_text}"
    )
    logger.info("Generando resumen de conversación")
    result = await generate_response(prompt, temperature=0.3)
    return result.text
