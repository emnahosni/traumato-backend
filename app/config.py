from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration globale de l'application chargée depuis les variables d'environnement."""

    DATABASE_URL: str = "postgresql+psycopg://traumato:traumato@localhost:5432/traumato"
    SECRET_KEY: str = "traumato-tunisie-secret-key-jwt-2026-traumatologie-secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 heures

    PROJECT_NAME: str = "TraumatoTN - Plateforme Médicale Traumatologie"
    API_V1_STR: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
