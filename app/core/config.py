"""
core/config.py
==============
Configuracion centralizada usando pydantic-settings.
Lee variables de entorno o del archivo .env automaticamente.
"""

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Base de datos ---
    DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:password@localhost:5432/reservas_db"
    )
    DB_ECHO_SQL: bool = False  # Poner True solo en entorno de desarrollo

    # --- Seguridad JWT, Anti-Fuerza Bruta y Mitigación DoS ---
    SECRET_KEY: str = "CAMBIA_ESTO_EN_PRODUCCION_usa_openssl_rand_hex_32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 5
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- App ---
    APP_TITLE: str = "Sistema de Reserva de Salas"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# Instancia global importable
settings = Settings()
