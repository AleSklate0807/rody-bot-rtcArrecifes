from datetime import UTC, datetime
from uuid import uuid4

from app.core.prompt_builder import build_prompt, build_welcome_message
from app.models.conversacion import Conversacion, Mensaje
from app.models.socio import Socio

NOW = datetime.now(UTC)


def _socio(**kw):
    return Socio(id=uuid4(), telegram_id=1, creado_en=NOW, **kw)


def _msg(conv, rol, txt):
    return Mensaje(
        id=uuid4(),
        conversacion_id=conv.id,
        socio_id=conv.socio_id,
        rol=rol,
        contenido=txt,
        creado_en=NOW,
    )


def test_build_prompt_roles_y_resumen():
    socio = _socio(nombre_display="Ana")
    conv = Conversacion(id=uuid4(), socio_id=socio.id, iniciada_en=NOW, resumen="Hablaron de actas.")
    hist = [_msg(conv, "user", "hola"), _msg(conv, "assistant", "¡Hola Ana!")]

    system, contents = build_prompt(socio, conv, hist, "¿qué es Rotaract?")

    assert "Sos Rody" in system and "Nombre: Ana" in system and "Hablaron de actas." in system
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[-1].parts[0].text == "¿qué es Rotaract?"


def test_welcome_escapa_nombre():
    msg = build_welcome_message(_socio(nombre_display="<b>x</b>"))
    assert "&lt;b&gt;x&lt;/b&gt;" in msg
