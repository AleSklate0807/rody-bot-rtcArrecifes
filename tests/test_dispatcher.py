import pytest

from app.bot import dispatcher


@pytest.fixture
def calls(monkeypatch):
    calls = []
    for name in ("handle_start", "handle_help", "handle_admin", "handle_unknown", "handle_message"):
        async def fake(*args, _n=name, **kwargs):
            calls.append((_n, args, kwargs))
        monkeypatch.setattr(dispatcher, name, fake)
    return calls


def _update(text, chat_type="private"):
    return {"update_id": 1, "message": {
        "message_id": 7, "text": text,
        "chat": {"id": 42, "type": chat_type},
        "from": {"id": 42, "first_name": "Ana"},
    }}


async def test_mensaje_normal(calls):
    await dispatcher.dispatch(_update("hola"))
    assert calls[0][0] == "handle_message"
    assert calls[0][2]["text"] == "hola"


async def test_comando_con_botname(calls):
    await dispatcher.dispatch(_update("/start@RodyBot"))
    assert calls[0][0] == "handle_start"


async def test_comando_admin_con_args(calls):
    await dispatcher.dispatch(_update("/aprobar 123"))
    assert calls[0] == ("handle_admin", (42, 42, "/aprobar", ["123"]), {})


async def test_ignora_grupos(calls):
    await dispatcher.dispatch(_update("hola", chat_type="group"))
    assert calls == []


async def test_comando_desconocido(calls):
    await dispatcher.dispatch(_update("/xyz"))
    assert calls[0][0] == "handle_unknown"
