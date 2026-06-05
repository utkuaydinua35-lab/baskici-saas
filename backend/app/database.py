"""
Veritabanı bağlantısı ve session yönetimi.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# psycopg3 sync engine — async sürüm sonra eklenebilir
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,  # SQL sorgularını basmak için True yap (debug)
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Tüm modeller bu Base'den türeyecek."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — her request için ayrı session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
