"""
Cliente de Supabase — operaciones de base de datos.

Todas las funciones son async usando asyncio.to_thread para no bloquear
el event loop de FastAPI con operaciones sincrónicas del cliente de Supabase.
"""
import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

from supabase import Client, create_client

from app.config.settings import settings
from app.models.conversacion import Conversacion, Mensaje
from app.models.documento import FragmentoRelevante
from app.models.socio import Socio

logger = logging.getLogger(__name__)

# Cliente singleton — se reutiliza entre invocaciones en el mismo contenedor
_client: Client | None = None


def _get_client() -> Client:
    """Retorna el cliente de Supabase, inicializándolo si es necesario."""
    global _client
    if _client is None:
        logger.info("Inicializando cliente Supabase")
        _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
    return _client


async def _run(func):
    """Ejecuta una función sincrónica de Supabase en un thread separado."""
    return await asyncio.to_thread(func)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ================================================================
# SOCIOS
# ================================================================

async def get_or_create_socio(
    telegram_id: int,
    username: str | None = None,
    nombre_display: str | None = None,
) -> tuple[Socio, bool]:
    """
    Busca un socio por telegram_id. Si no existe, lo crea.
    Actualiza el último acceso en cada llamada.

    Los nuevos socios quedan inactivos (pendientes de aprobación) salvo que
    sean admins o que ACCESO_ABIERTO esté habilitado.

    Returns:
        (socio, creado) — creado es True si el socio se registró recién.
    """
    client = _get_client()
    es_admin = telegram_id in settings.admin_ids

    result = await _run(
        lambda: client.table("socios").select("*").eq("telegram_id", telegram_id).execute()
    )

    if result.data:
        socio_data = result.data[0]
        update_data: dict = {"ultimo_acceso": _now_iso()}
        if username and username != socio_data.get("username"):
            update_data["username"] = username
        if es_admin and not (socio_data.get("es_admin") and socio_data.get("activo")):
            update_data.update(es_admin=True, activo=True)

        result = await _run(
            lambda: client.table("socios")
            .update(update_data)
            .eq("telegram_id", telegram_id)
            .execute()
        )
        return Socio(**(result.data[0] if result.data else {**socio_data, **update_data})), False

    logger.info(f"Registrando nuevo socio: telegram_id={telegram_id}")
    new_socio = {
        "telegram_id": telegram_id,
        "username": username,
        "nombre_display": nombre_display,
        "es_admin": es_admin,
        "activo": es_admin or settings.ACCESO_ABIERTO,
        "ultimo_acceso": _now_iso(),
    }
    result = await _run(lambda: client.table("socios").insert(new_socio).execute())
    return Socio(**result.data[0]), True


async def set_socio_activo(telegram_id: int, activo: bool) -> Socio | None:
    """Habilita o deshabilita a un socio. Retorna None si no existe."""
    client = _get_client()
    result = await _run(
        lambda: client.table("socios")
        .update({"activo": activo})
        .eq("telegram_id", telegram_id)
        .execute()
    )
    return Socio(**result.data[0]) if result.data else None


async def list_pending_socios(limit: int = 30) -> list[Socio]:
    """Socios registrados que todavía no fueron aprobados."""
    client = _get_client()
    result = await _run(
        lambda: client.table("socios")
        .select("*")
        .eq("activo", False)
        .order("creado_en", desc=True)
        .limit(limit)
        .execute()
    )
    return [Socio(**s) for s in result.data]


# ================================================================
# IDEMPOTENCIA
# ================================================================

async def is_update_processed(update_id: int) -> bool:
    """Retorna True si el update ya fue procesado (evita duplicados)."""
    client = _get_client()
    result = await _run(
        lambda: client.table("updates_procesados")
        .select("update_id")
        .eq("update_id", update_id)
        .execute()
    )
    return bool(result.data)


async def mark_update_processed(update_id: int) -> None:
    """Registra un update como procesado."""
    client = _get_client()
    try:
        await _run(
            lambda: client.table("updates_procesados").insert({"update_id": update_id}).execute()
        )
    except Exception as e:
        # Si ya existe (race condition), ignorar
        logger.warning(f"update_id {update_id} ya estaba registrado: {e}")


# ================================================================
# CONVERSACIONES
# ================================================================

async def get_active_conversation(socio_id: UUID) -> Conversacion | None:
    """Retorna la conversación más reciente sin cerrar del socio, o None."""
    client = _get_client()
    result = await _run(
        lambda: client.table("conversaciones")
        .select("*")
        .eq("socio_id", str(socio_id))
        .is_("cerrada_en", "null")
        .order("iniciada_en", desc=True)
        .limit(1)
        .execute()
    )
    return Conversacion(**result.data[0]) if result.data else None


async def create_conversation(socio_id: UUID, resumen: str | None = None) -> Conversacion:
    """Crea una nueva conversación, opcionalmente arrastrando el resumen de la anterior."""
    client = _get_client()
    data: dict = {"socio_id": str(socio_id)}
    if resumen:
        data["resumen"] = resumen
    result = await _run(lambda: client.table("conversaciones").insert(data).execute())
    logger.info(f"Nueva conversación creada para socio {socio_id}")
    return Conversacion(**result.data[0])


async def close_conversation(conversacion_id: UUID) -> None:
    """Marca una conversación como cerrada."""
    client = _get_client()
    await _run(
        lambda: client.table("conversaciones")
        .update({"cerrada_en": _now_iso()})
        .eq("id", str(conversacion_id))
        .execute()
    )


async def update_conversation(
    conversacion_id: UUID,
    resumen: str | None = None,
    total_turnos: int | None = None,
    tokens_usados: int | None = None,
) -> None:
    """Actualiza campos de una conversación."""
    client = _get_client()
    update_data: dict = {}
    if resumen is not None:
        update_data["resumen"] = resumen
    if total_turnos is not None:
        update_data["total_turnos"] = total_turnos
    if tokens_usados is not None:
        update_data["tokens_usados"] = tokens_usados

    if update_data:
        await _run(
            lambda: client.table("conversaciones")
            .update(update_data)
            .eq("id", str(conversacion_id))
            .execute()
        )


# ================================================================
# MENSAJES
# ================================================================

async def get_recent_messages(conversacion_id: UUID, limit: int = 20) -> list[Mensaje]:
    """
    Retorna los N mensajes más recientes de una conversación,
    ordenados cronológicamente (el más antiguo primero).
    """
    client = _get_client()
    result = await _run(
        lambda: client.table("mensajes")
        .select("*")
        .eq("conversacion_id", str(conversacion_id))
        .order("creado_en", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed([Mensaje(**m) for m in result.data]))


async def save_message(
    conversacion_id: UUID,
    socio_id: UUID,
    rol: str,
    contenido: str,
    tokens_entrada: int | None = None,
    tokens_salida: int | None = None,
) -> Mensaje:
    """Persiste un mensaje en la base de datos."""
    client = _get_client()
    data: dict = {
        "conversacion_id": str(conversacion_id),
        "socio_id": str(socio_id),
        "rol": rol,
        "contenido": contenido,
    }
    if tokens_entrada is not None:
        data["tokens_entrada"] = tokens_entrada
    if tokens_salida is not None:
        data["tokens_salida"] = tokens_salida

    result = await _run(lambda: client.table("mensajes").insert(data).execute())
    return Mensaje(**result.data[0])


# ================================================================
# DOCUMENTOS (RAG)
# ================================================================

async def search_fragmentos(
    embedding: list[float],
    limite: int = 5,
    similitud_minima: float = 0.6,
) -> list[FragmentoRelevante]:
    """Fragmentos de documentos más similares al embedding de la consulta."""
    client = _get_client()
    vector = "[" + ",".join(f"{v:.7f}" for v in embedding) + "]"
    result = await _run(
        lambda: client.rpc(
            "match_fragmentos",
            {"query_embedding": vector, "match_count": limite, "min_similarity": similitud_minima},
        ).execute()
    )
    return [FragmentoRelevante(**f) for f in result.data or []]


async def get_textos_documentos(titulos: list[str]) -> dict[str, list[str]]:
    """Fragmentos (en orden) de los documentos indicados, agrupados por título."""
    client = _get_client()
    docs = await _run(
        lambda: client.table("documentos").select("id, titulo").in_("titulo", titulos).execute()
    )
    resultado: dict[str, list[str]] = {}
    for doc in docs.data or []:
        frags = await _run(
            lambda d=doc: client.table("documento_fragmentos")
            .select("contenido")
            .eq("documento_id", d["id"])
            .order("orden")
            .execute()
        )
        resultado[doc["titulo"]] = [f["contenido"] for f in frags.data or []]
    return resultado
