from app.core.chunking import fragmentar, limpiar_lineas


def test_limpia_invisibles_y_numeros_de_pagina():
    assert limpiar_lineas("4.​ Junta  directiva\n\n12\nfin") == ["4. Junta directiva", "fin"]


def test_respeta_tamano_maximo_y_paginas():
    paginas = ["\n".join(f"linea {p}-{i} " + "x" * 60 for i in range(30)) for p in range(3)]
    frags = fragmentar(paginas, max_chars=500, solapamiento=100)
    assert len(frags) > 3
    assert all(len(f.contenido) <= 500 for f in frags)
    assert frags[0].pagina == 1 and frags[-1].pagina == 3


def test_solapamiento_entre_fragmentos():
    frags = fragmentar(["\n".join(f"oración número {i}" for i in range(100))], max_chars=200, solapamiento=50)
    lineas_0 = frags[0].contenido.splitlines()
    lineas_1 = frags[1].contenido.splitlines()
    # El segundo fragmento arranca repitiendo el final del primero (≤ 50 caracteres)
    repetidas = lineas_1[: lineas_1.index(lineas_0[-1]) + 1]
    assert repetidas == lineas_0[-len(repetidas):]
    assert 0 < sum(len(x) + 1 for x in repetidas) <= 50 + 1


def test_linea_larga_se_parte():
    frags = fragmentar(["palabra " * 400], max_chars=300, solapamiento=0)
    assert all(len(f.contenido) <= 300 for f in frags)


def test_documento_vacio():
    assert fragmentar(["", "  \n 3 \n"]) == []
