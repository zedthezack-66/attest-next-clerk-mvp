import os
from datetime import datetime, timezone

from sqlalchemy import JSON, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://attest:attest@localhost:5432/attest")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

# Postgres gets JSONB / pgvector; other dialects (SQLite in tests) fall back to plain JSON.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def vector_type(dim: int = EMBEDDING_DIM):
    from pgvector.sqlalchemy import Vector

    return JSON().with_variant(Vector(dim), "postgresql")


def utcnow() -> datetime:
    """Naive UTC timestamp, matching the `timestamp without time zone` columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def is_postgres(db) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def set_tenant(db, tenant_id: str) -> None:
    if is_postgres(db):
        db.execute(text("select set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id})
