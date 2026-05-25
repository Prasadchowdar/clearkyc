"""Extractor selection based on configuration (one env var switches providers)."""

from __future__ import annotations

from ..config import settings
from .base import DocumentExtractor
from .mock import MockDocumentExtractor


def get_extractor() -> DocumentExtractor:
    if settings.extractor == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "EXTRACTOR=openai but OPENAI_API_KEY is not set. "
                "Add it to a gitignored .env or the environment."
            )
        # Imported lazily so the OpenAI SDK is only needed in openai mode.
        from .openai_extractor import OpenAIDocumentExtractor

        return OpenAIDocumentExtractor(settings.openai_api_key, settings.openai_model)
    return MockDocumentExtractor()
