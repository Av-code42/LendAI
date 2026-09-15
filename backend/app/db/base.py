import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings


def _normalize_database_url(url: str) -> str:
    """Managed Postgres providers (Neon, Supabase, Render, ...) hand out
    plain postgres:// or postgresql:// URLs -- SQLAlchemy needs the
    driver named explicitly for the psycopg2 dialect."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    return url


# Vercel sets VERCEL=1 in every serverless invocation. Each invocation may
# run in a fresh (or briefly-reused) execution environment, so a
# process-lifetime connection pool sized for a long-lived server doesn't
# make sense -- NullPool opens a fresh connection per checkout instead.
# Use a pooled/pgbouncer-style connection string from your Postgres
# provider (Neon's "Pooled connection" string, etc.) so this doesn't
# overwhelm the database with connection churn.
_is_serverless = bool(os.environ.get("VERCEL"))

engine = create_engine(
    _normalize_database_url(settings.database_url),
    pool_pre_ping=True,
    poolclass=NullPool if _is_serverless else None,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
