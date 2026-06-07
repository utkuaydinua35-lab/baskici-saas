"""
Uygulama yapılandırması. Env değişkenlerini Pydantic ile tip güvenli okur.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = Field(..., alias="DATABASE_URL")

    # Auth
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 gün
    session_secret: str = Field(..., alias="SESSION_SECRET")

    # Environment
    env: str = Field("development", alias="ENV")
    host: str = Field("127.0.0.1", alias="HOST")
    port: int = Field(8000, alias="PORT")

    # OAuth
    google_client_id: str = Field("", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field("", alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        "http://localhost:8000/api/auth/google/callback",
        alias="GOOGLE_REDIRECT_URI",
    )

    # Frontend
    frontend_url: str = Field("http://localhost:5173", alias="FRONTEND_URL")
    backend_url: str = Field("http://localhost:8000", alias="BACKEND_URL")

    # Public sipariş takip — hangi Shopify mağazasi sorgulanacak (store_url ile eşleşir)
    tracker_shop_domain: str = Field("2eb3e1-48.myshopify.com", alias="TRACKER_SHOP_DOMAIN")

    # Destek görsellerinin servis edildiği public taban URL
    support_public_base_url: str = Field("https://siparistakip.bernzcompany.com", alias="SUPPORT_PUBLIC_BASE_URL")

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
