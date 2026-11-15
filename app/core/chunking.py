"""
Fragmentación de documentos para RAG.

Divide el texto de un PDF (una cadena por página) en fragmentos de tamaño
acotado, con solapamiento entre fragmentos consecutivos para no perder
contexto en los cortes. Cada fragmento recuerda la página donde empieza.
"""
import re
from dataclasses import dataclass

_INVISIBLES = re.compile(r"[​‌‍­﻿]")
_SOLO_NUMERO = re.compile(r"^\d{1,3}$")  # números de página sueltos


@dataclass
class FragmentoTexto:
    contenido: str
    pagina: int  # 1-indexada


def limpiar_lineas(texto: str) -> list[str]:
    """Normaliza el texto de una página y devuelve sus líneas no vacías."""
    texto = _INVISIBLES.sub("", texto)
    lineas = []
    for linea in texto.splitlines():
        linea = " ".join(linea.split())
        if linea and not _SOLO_NUMERO.match(linea):
            lineas.append(linea)
    return lineas


def fragmentar(paginas: list[str], max_chars: int = 1200, solapamiento: int = 200) -> list[FragmentoTexto]:
    """
    Agrupa las líneas del documento en fragmentos de hasta `max_chars`.
    Cada fragmento nuevo arranca con las últimas líneas del anterior
    (hasta `solapamiento` caracteres).
    """
    unidades: list[tuple[str, int]] = []
    for num_pagina, texto in enumerate(paginas, start=1):
        for linea in limpiar_lineas(texto):
            # Líneas larguísimas (texto sin saltos) se parten en trozos
            while len(linea) > max_chars:
                corte = linea.rfind(" ", 0, max_chars)
                corte = corte if corte > 0 else max_chars
                unidades.append((linea[:corte], num_pagina))
                linea = linea[corte:].strip()
            if linea:
                unidades.append((linea, num_pagina))

    fragmentos: list[FragmentoTexto] = []
    actual: list[tuple[str, int]] = []
    largo = 0

    for unidad in unidades:
        lleno = largo + len(unidad[0]) + 1 > max_chars
        # Un cambio de página suele ser un cambio de tema: si el fragmento ya
        # tiene un tamaño razonable, se corta ahí para no mezclar temas.
        cambio_pagina = largo >= max_chars // 3 and unidad[1] != actual[-1][1] if actual else False
        if actual and (lleno or cambio_pagina):
            fragmentos.append(_emitir(actual))
            # Solapamiento: conservar las últimas líneas del fragmento emitido
            cola: list[tuple[str, int]] = []
            largo_cola = 0
            for previa in reversed(actual):
                if largo_cola + len(previa[0]) > solapamiento:
                    break
                cola.insert(0, previa)
                largo_cola += len(previa[0]) + 1
            actual, largo = cola, largo_cola
        actual.append(unidad)
        largo += len(unidad[0]) + 1

    if actual:
        fragmentos.append(_emitir(actual))
    return fragmentos


def _emitir(unidades: list[tuple[str, int]]) -> FragmentoTexto:
    return FragmentoTexto(contenido="\n".join(u[0] for u in unidades), pagina=unidades[0][1])
