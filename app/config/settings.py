import logging
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ---- Telegram ----
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str

    # ---- Supabase ----
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # ---- Google AI ----
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-3.5-flash"

    # ---- App ----
    BOT_ENVIRONMENT: Literal["production", "development"] = "production"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ---- Control de acceso ----
    # IDs de Telegram (separados por coma) con permisos de administrador.
    # Los admins quedan habilitados automáticamente y pueden aprobar socios.
    ADMIN_TELEGRAM_IDS: str = ""
    # Si es True, cualquier persona que escriba queda habilitada sin aprobación.
    ACCESO_ABIERTO: bool = False

    # ---- Límites de conversación ----
    MAX_RECENT_TURNS: int = 10          # Turnos recientes a incluir en el prompt
    SUMMARY_TRIGGER_TURNS: int = 15     # Turnos antes de resumir y rotar la conversación

    # ---- Búsqueda en documentos (RAG) ----
    RAG_TOP_K: int = 8                  # Fragmentos a incluir en el prompt
    RAG_MIN_SIMILARITY: float = 0.62    # Similitud coseno mínima para considerar relevante
    # Documentos cortos con datos centrales del club que van SIEMPRE completos en el
    # prompt, en vez de depender de la búsqueda. Títulos separados por ";".
    RAG_DOCUMENTOS_FIJOS: str = "Información de Rotaract Club Arrecifes"

    @property
    def log_level_int(self) -> int:
        return getattr(logging, self.LOG_LEVEL)

    @property
    def documentos_fijos(self) -> list[str]:
        return [t.strip() for t in self.RAG_DOCUMENTOS_FIJOS.split(";") if t.strip()]

    @property
    def admin_ids(self) -> set[int]:
        return {
            int(x) for x in self.ADMIN_TELEGRAM_IDS.replace(" ", "").split(",") if x
        }


# Instancia global — se inicializa una vez al arrancar la función
settings = Settings()
