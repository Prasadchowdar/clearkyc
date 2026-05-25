"""Unit tests for the mock embedder (deterministic, no API/DB)."""

from app.embeddings import MockEmbedder
from app.models import EMBED_DIM


def _cos(a, b):
    # Vectors are L2-normalized, so dot product == cosine similarity.
    return sum(x * y for x, y in zip(a, b))


def test_dimension_and_determinism():
    e = MockEmbedder()
    v1 = e.embed("merchant kyc name mismatch")
    v2 = e.embed("merchant kyc name mismatch")
    assert len(v1) == EMBED_DIM
    assert v1 == v2  # deterministic -> reproducible evals


def test_similar_text_is_closer_than_unrelated():
    e = MockEmbedder()
    query = e.embed("merchant name mismatch across PAN and bank documents")
    near = e.embed("name consistency across PAN GST bank documents")
    far = e.embed("weather forecast cricket score tomorrow evening")
    assert _cos(query, near) > _cos(query, far)
