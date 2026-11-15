from app.services.telegram_format import format_model_output, html_to_plain, split_message


def test_escapa_caracteres_html():
    assert format_model_output("2 < 3 & 5 > 4") == "2 &lt; 3 &amp; 5 &gt; 4"


def test_conserva_etiquetas_permitidas():
    assert format_model_output("<b>hola</b> <i>che</i>") == "<b>hola</b> <i>che</i>"


def test_escapa_etiquetas_no_permitidas():
    assert format_model_output("<script>x</script>") == "&lt;script&gt;x&lt;/script&gt;"


def test_convierte_markdown():
    assert format_model_output("**Rotaract**") == "<b>Rotaract</b>"
    assert format_model_output("## Título") == "<b>Título</b>"
    assert format_model_output("* uno\n* dos") == "- uno\n- dos"
    assert format_model_output("usá `/ayuda`") == "usá <code>/ayuda</code>"


def test_html_to_plain():
    assert html_to_plain("<b>a &amp; b</b>") == "a & b"


def test_split_respeta_limite_y_contenido():
    text = "\n".join(f"línea {i} " + "x" * 50 for i in range(200))
    chunks = split_message(text, limit=1000)
    assert len(chunks) > 1
    assert all(len(c) <= 1000 for c in chunks)
    assert "".join(c.replace("\n", "") for c in chunks) == text.replace("\n", "")


def test_split_texto_corto():
    assert split_message("hola") == ["hola"]
