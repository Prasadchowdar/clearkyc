"""Database engine, session factory, and declarative base.

One Postgres instance (with the pgvector extension enabled) is the single
source of truth for relational data AND, from Phase 2 onward, rule embeddings
for RAG. Keeping both in one store is a deliberate simplicity choice.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI dependency that yields a scoped session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
