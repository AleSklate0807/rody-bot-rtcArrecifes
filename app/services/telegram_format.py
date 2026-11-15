"""
Formateo de texto para Telegram (parse_mode=HTML).

Telegram rechaza el mensaje entero si el HTML es inválido, así que la
salida del modelo se escapa por completo y solo se re-habilitan unas
pocas etiquetas seguras. También se convierte el markdown más común.
"""
import html
import re

# Telegram admite hasta 4096 caracteres; dejamos margen para el escape.
MAX_CHUNK = 3500

_ALLOWED_TAGS = re.compile(r"&lt;(/?)(b|i|u|s|code|pre)&gt;", re.IGNORECASE)
_ANY_TAG = re.compile(r"<[^>]+>")


def format_model_output(text: str) -> str:
    """Convierte la respuesta del modelo a HTML seguro para Telegram."""
    out = html.escape(text, quote=False)
    out = _ALLOWED_TAGS.sub(lambda m: f"<{m.group(1)}{m.group(2).lower()}>", out)
    # Markdown → HTML
    out = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", out, flags=re.DOTALL)
    out = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", out)
    out = re.sub(r"^#{1,6}\s+(.+)$", r"<b>\1</b>", out, flags=re.MULTILINE)
    out = re.sub(r"^(\s*)\* ", r"\1- ", out, flags=re.MULTILINE)
    return out


def html_to_plain(text: str) -> str:
    """Quita etiquetas y des-escapa entidades (fallback si el HTML falla)."""
    return html.unescape(_ANY_TAG.sub("", text))


def split_message(text: str, limit: int = MAX_CHUNK) -> list[str]:
    """Divide un texto largo en partes, cortando preferentemente en saltos de línea."""
    chunks: list[str] = []
    rest = text
    while len(rest) > limit:
        cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks
