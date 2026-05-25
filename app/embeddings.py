"""Embeddings layer (provider-agnostic).

- MockEmbedder: deterministic hashed bag-of-words vector. Free, offline, and
  good enough that texts sharing words land closer in cosine space — which is
  all the RAG retrieval demo/tests need.
- OpenAIEmbedder: text-embedding-3-small (1536 dims).

Both emit EMBED_DIM-length vectors so the pgvector column is provider-neutral.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from .config import settings
from .models import EMBED_DIM

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class MockEmbedder:
    def embed(self, text: str) -> list[float]:
        vec = [0.0] * EMBED_DIM
        for tok in _tokens(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % EMBED_DIM
            sign = 1.0 if (h >> 64) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class OpenAIEmbedder:
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [d.embedding for d in resp.data]

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]


def get_embedder() -> Embedder:
    if settings.embedder == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("EMBEDDER=openai but OPENAI_API_KEY is not set.")
        return OpenAIEmbedder(settings.openai_api_key, settings.openai_embedding_model)
    return MockEmbedder()
