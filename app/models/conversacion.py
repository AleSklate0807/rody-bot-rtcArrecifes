from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID


class Conversacion(BaseModel):
    """Representa una sesión de conversación de un socio con el bot."""
    id: UUID
    socio_id: UUID
    iniciada_en: datetime
    cerrada_en: Optional[datetime] = None
    resumen: Optional[str] = None       # Resumen comprimido por Gemini
    total_turnos: int = 0
    tokens_usados: int = 0


class Mensaje(BaseModel):
    """Representa un mensaje individual dentro de una conversación."""
    id: UUID
    conversacion_id: UUID
    socio_id: UUID
    rol: Literal["user", "assistant", "system"]
    contenido: str
    tokens_entrada: Optional[int] = None
    tokens_salida: Optional[int] = None
    creado_en: datetime


class MensajeInput(BaseModel):
    """DTO para insertar un nuevo mensaje (sin ID ni timestamps)."""
    conversacion_id: UUID
    socio_id: UUID
    rol: Literal["user", "assistant", "system"]
    contenido: str
    tokens_entrada: Optional[int] = None
    tokens_salida: Optional[int] = None

