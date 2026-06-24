"""
Veritabanı bağlantısı ve session yönetimi.
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker, with_loader_criteria

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


# ─── Global soft-delete filtresi ──────────────────────────────
# Order (orders/telafiler) SELECT'lerine otomatik "deleted_at IS NULL" ekler.
# Cop kutusu / geri-al sorgulari .execution_options(include_deleted=True) ile opt-out eder.
@event.listens_for(SessionLocal, "do_orm_execute")
def _soft_delete_filter(execute_state):
    if (
        execute_state.is_select
        and not execute_state.is_column_load
        and not execute_state.execution_options.get("include_deleted", False)
    ):
        from app.models import Order  # lazy import (circular onleme)
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                Order,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )


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
