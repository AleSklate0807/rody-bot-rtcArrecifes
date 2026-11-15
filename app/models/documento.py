from uuid import UUID

from pydantic import BaseModel


class FragmentoRelevante(BaseModel):
    """Fragmento de un documento recuperado por la búsqueda semántica."""
    id: UUID
    documento_id: UUID
    titulo: str
    pagina: int | None = None
    contenido: str
    similitud: float
