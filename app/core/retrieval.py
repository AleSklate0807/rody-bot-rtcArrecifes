"""
Recuperación de contexto (RAG).

Dos fuentes:
- Documentos fijos: textos cortos con los datos centrales del club que van
  siempre completos en el prompt (se cachean unos minutos por instancia).
- Búsqueda semántica: los fragmentos más relevantes del resto de los documentos.
"""
import logging
import time

from app.config.settings import settings
from app.models.conversacion import Mensaje
from app.models.documento import FragmentoRelevante
from app.services.gemini import embed_query
from app.services.supabase_client import get_textos_documentos, search_fragmentos

logger = logging.getLogger(__name__)

# Preguntas cortas suelen ser repreguntas ("¿y el vicepresidente?"):
# se buscan junto con el mensaje anterior del socio para no perder el tema.
_UMBRAL_REPREGUNTA = 60

_CACHE_TTL = 600  # segundos
_cache_fijos: tuple[float, dict[str, str]] | None = None


def armar_consulta(pregunta: str, mensajes_recientes: list[Mensaje]) -> str:
    if len(pregunta) >= _UMBRAL_REPREGUNTA:
        return pregunta
    anteriores = [m.contenido for m in mensajes_recientes if m.rol == "user"]
    return f"{anteriores[-1]}\n{pregunta}" if anteriores else pregunta


def unir_fragmentos(fragmentos: list[str]) -> str:
    """Reconstruye el texto de un documento quitando las líneas repetidas por el solapamiento."""
    lineas: list[str] = []
    for fragmento in fragmentos:
        nuevas = fragmento.splitlines()
        solapadas = 0
        for k in range(min(len(lineas), len(nuevas)), 0, -1):
            if lineas[-k:] == nuevas[:k]:
                solapadas = k
                break
        lineas += nuevas[solapadas:]
    return "\n".join(lineas)


async def obtener_documentos_fijos() -> dict[str, str]:
    """Texto completo de los documentos fijos, por título (vacío si falla)."""
    global _cache_fijos
    if not settings.documentos_fijos:
        return {}
    if _cache_fijos and time.monotonic() - _cache_fijos[0] < _CACHE_TTL:
        return _cache_fijos[1]
    try:
        por_titulo = await get_textos_documentos(settings.documentos_fijos)
    except Exception as e:
        logger.error(f"Error al obtener documentos fijos: {e}", exc_info=True)
        return _cache_fijos[1] if _cache_fijos else {}
    textos = {titulo: unir_fragmentos(frags) for titulo, frags in por_titulo.items()}
    _cache_fijos = (time.monotonic(), textos)
    return textos


async def buscar_contexto(pregunta: str, mensajes_recientes: list[Mensaje]) -> list[FragmentoRelevante]:
    """Fragmentos relevantes de los documentos no fijos (lista vacía si falla la búsqueda)."""
    fijos = set(settings.documentos_fijos)
    try:
        embedding = await embed_query(armar_consulta(pregunta, mensajes_recientes))
        fragmentos = await search_fragmentos(
            embedding,
            limite=settings.RAG_TOP_K + 3,  # margen por si vienen fragmentos de documentos fijos
            similitud_minima=settings.RAG_MIN_SIMILARITY,
        )
    except Exception as e:
        # Sin documentos Rody igual puede responder; no cortamos la conversación
        logger.error(f"Error al buscar en documentos: {e}", exc_info=True)
        return []

    fragmentos = [f for f in fragmentos if f.titulo not in fijos][: settings.RAG_TOP_K]
    logger.info(
        "RAG: %d fragmentos (%s)",
        len(fragmentos),
        ", ".join(f"{f.titulo} p.{f.pagina} {f.similitud:.2f}" for f in fragmentos),
    )
    return fragmentos
