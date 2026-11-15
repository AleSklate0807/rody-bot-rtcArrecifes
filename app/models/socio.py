from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from uuid import UUID


class Socio(BaseModel):
    """Representa un socio del club identificado por su Telegram ID."""
    id: UUID
    telegram_id: int
    username: Optional[str] = None
    nombre_display: Optional[str] = None
    es_admin: bool = False
    activo: bool = True
    creado_en: datetime
    ultimo_acceso: Optional[datetime] = None

    @property
    def nombre(self) -> str:
        """Retorna el nombre más apropiado disponible para el socio."""
        if self.nombre_display:
            return self.nombre_display
        if self.username:
            return f"@{self.username}"
        return f"Socio {self.telegram_id}"

