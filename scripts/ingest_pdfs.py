"""
Carga documentos PDF en la base de conocimiento de Rody.

Extrae el texto, lo divide en fragmentos, genera embeddings con Gemini y
los guarda en Supabase. Si un PDF ya fue cargado y no cambió, se saltea;
si cambió, se reemplaza. El título que Rody cita es el nombre del archivo.

Uso:
    python scripts/ingest_pdfs.py                  # carga todo docs/pdfs/
    python scripts/ingest_pdfs.py archivo.pdf ...  # carga archivos puntuales
    python scripts/ingest_pdfs.py --forzar         # recarga aunque no haya cambios
    python scripts/ingest_pdfs.py --listar         # muestra lo cargado
    python scripts/ingest_pdfs.py --borrar "Nombre del archivo.pdf"
"""
import argparse
import hashlib
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymupdf  # noqa: E402

from app.core.chunking import fragmentar  # noqa: E402
from app.services.gemini import embed_documents  # noqa: E402
from app.services.supabase_client import _get_client  # noqa: E402

CARPETA_DEFAULT = Path(__file__).resolve().parent.parent / "docs" / "pdfs"
LOTE_EMBEDDINGS = 40
LOTE_INSERT = 50


# La cuota gratuita de Gemini permite 100 embeddings por minuto (cada texto
# de un lote cuenta como uno). Dejamos margen para las consultas del bot.
CUOTA_POR_MINUTO = 80
_enviados: list[tuple[float, int]] = []


def _respetar_cuota(cantidad: int) -> None:
    """Espera lo necesario para no superar CUOTA_POR_MINUTO en la última ventana de 60 s."""
    while True:
        ahora = time.monotonic()
        _enviados[:] = [(t, n) for t, n in _enviados if ahora - t < 60]
        if sum(n for _, n in _enviados) + cantidad <= CUOTA_POR_MINUTO:
            _enviados.append((ahora, cantidad))
            return
        espera = 60 - (ahora - _enviados[0][0]) + 1
        print(f"  esperando {espera:.0f}s por la cuota de embeddings...")
        time.sleep(espera)


def _vector(valores: list[float]) -> str:
    """Formato de texto que pgvector acepta vía la REST API."""
    return "[" + ",".join(f"{v:.7f}" for v in valores) + "]"


def cargar(ruta: Path, forzar: bool) -> None:
    db = _get_client()
    contenido = ruta.read_bytes()
    hash_pdf = hashlib.sha256(contenido).hexdigest()
    titulo = ruta.stem

    existente = db.table("documentos").select("id, hash").eq("archivo", ruta.name).execute().data
    if existente and existente[0]["hash"] == hash_pdf and not forzar:
        print(f"= {ruta.name}: sin cambios, se saltea")
        return

    with pymupdf.open(stream=contenido, filetype="pdf") as pdf:
        paginas = [p.get_text() for p in pdf]
    fragmentos = fragmentar(paginas)
    if not fragmentos:
        print(f"! {ruta.name}: no se encontró texto (¿es un PDF escaneado?)")
        return

    print(f"→ {ruta.name}: {len(paginas)} páginas, {len(fragmentos)} fragmentos")

    embeddings: list[list[float]] = []
    for i in range(0, len(fragmentos), LOTE_EMBEDDINGS):
        lote = [f.contenido for f in fragmentos[i : i + LOTE_EMBEDDINGS]]
        _respetar_cuota(len(lote))
        embeddings += embed_documents(lote, titulo=titulo)
        print(f"  embeddings {len(embeddings)}/{len(fragmentos)}")

    # Reemplazar la versión anterior (los fragmentos se borran en cascada)
    if existente:
        db.table("documentos").delete().eq("id", existente[0]["id"]).execute()

    doc = db.table("documentos").insert({
        "titulo": titulo,
        "archivo": ruta.name,
        "hash": hash_pdf,
        "paginas": len(paginas),
        "total_fragmentos": len(fragmentos),
    }).execute().data[0]

    try:
        filas = [
            {
                "documento_id": doc["id"],
                "orden": i,
                "pagina": f.pagina,
                "contenido": f.contenido,
                "embedding": _vector(e),
            }
            for i, (f, e) in enumerate(zip(fragmentos, embeddings, strict=True))
        ]
        for i in range(0, len(filas), LOTE_INSERT):
            db.table("documento_fragmentos").insert(filas[i : i + LOTE_INSERT]).execute()
    except Exception:
        db.table("documentos").delete().eq("id", doc["id"]).execute()
        raise

    print(f"✅ {ruta.name}: cargado")


def listar() -> None:
    docs = _get_client().table("documentos").select("*").order("titulo").execute().data
    if not docs:
        print("No hay documentos cargados.")
    for d in docs:
        detalle = f"{d['paginas']} págs, {d['total_fragmentos']} fragmentos, {d['cargado_en'][:10]}"
        print(f"- {d['titulo']}  ({detalle})")


def borrar(archivo: str) -> None:
    res = _get_client().table("documentos").delete().eq("archivo", archivo).execute()
    print(f"🗑️ Borrado: {archivo}" if res.data else f"No encontré '{archivo}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga PDFs en la base de conocimiento de Rody")
    parser.add_argument("archivos", nargs="*", type=Path, help=f"PDFs a cargar (default: {CARPETA_DEFAULT})")
    parser.add_argument("--forzar", action="store_true", help="recargar aunque el PDF no haya cambiado")
    parser.add_argument("--listar", action="store_true", help="listar documentos cargados")
    parser.add_argument("--borrar", metavar="ARCHIVO", help="borrar un documento por nombre de archivo")
    args = parser.parse_args()

    if args.listar:
        return listar()
    if args.borrar:
        return borrar(args.borrar)

    rutas = args.archivos or sorted(CARPETA_DEFAULT.glob("*.pdf"))
    if not rutas:
        sys.exit(f"No hay PDFs en {CARPETA_DEFAULT}")
    errores = 0
    for ruta in rutas:
        try:
            cargar(ruta, args.forzar)
        except Exception as e:
            errores += 1
            print(f"❌ {ruta.name}: {e}")
    sys.exit(1 if errores else 0)


if __name__ == "__main__":
    main()
