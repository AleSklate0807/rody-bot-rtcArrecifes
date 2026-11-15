from datetime import UTC, datetime
from uuid import uuid4

from app.core.prompt_builder import build_prompt
from app.core.retrieval import armar_consulta
from app.models.conversacion import Conversacion, Mensaje
from app.models.documento import FragmentoRelevante
from app.models.socio import Socio

NOW = datetime.now(UTC)


def _msg(rol, txt):
    return Mensaje(
        id=uuid4(), conversacion_id=uuid4(), socio_id=uuid4(), rol=rol, contenido=txt, creado_en=NOW
    )


def test_repregunta_corta_incluye_mensaje_anterior():
    hist = [_msg("user", "¿Quién es la presidenta del club?"), _msg("assistant", "Es X.")]
    assert armar_consulta("¿y el tesorero?", hist) == "¿Quién es la presidenta del club?\n¿y el tesorero?"


def test_pregunta_larga_va_sola():
    pregunta = "¿Cuáles son los requisitos para postularse a presidente del club según el reglamento?"
    assert armar_consulta(pregunta, [_msg("user", "hola")]) == pregunta


def test_prompt_incluye_documentos_con_fuente():
    socio = Socio(id=uuid4(), telegram_id=1, creado_en=NOW)
    conv = Conversacion(id=uuid4(), socio_id=socio.id, iniciada_en=NOW)
    frag = FragmentoRelevante(
        id=uuid4(), documento_id=uuid4(), titulo="Reglamento Interno", pagina=7,
        contenido="La elección se celebrará antes del 31 de diciembre.", similitud=0.8,
    )
    system, _ = build_prompt(socio, conv, [], "¿cuándo se elige presidente?", fragmentos=[frag])
    assert 'fuente="Reglamento Interno, pág. 7"' in system
    assert "31 de diciembre" in system


def test_prompt_sin_documentos():
    socio = Socio(id=uuid4(), telegram_id=1, creado_en=NOW)
    conv = Conversacion(id=uuid4(), socio_id=socio.id, iniciada_en=NOW)
    system, _ = build_prompt(socio, conv, [], "hola")
    assert "DOCUMENTOS DEL CLUB (fragmentos" not in system


def test_unir_fragmentos_quita_solapamiento():
    from app.core.retrieval import unir_fragmentos

    assert unir_fragmentos(["a\nb\nc", "b\nc\nd", "e"]) == "a\nb\nc\nd\ne"
