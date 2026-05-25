"""Retrieval over the compliance knowledge base (pgvector cosine search)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import models
from .embeddings import Embedder, get_embedder


def retrieve_rules(
    db: Session, query: str, k: int = 4, embedder: Embedder | None = None
) -> list[models.Rule]:
    """Return the k most semantically relevant rules for `query`."""
    embedder = embedder or get_embedder()
    qv = embedder.embed(query)
    return (
        db.query(models.Rule)
        .filter(models.Rule.embedding.is_not(None))
        .order_by(models.Rule.embedding.cosine_distance(qv))
        .limit(k)
        .all()
    )
