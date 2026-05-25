"""Reasoner selection based on configuration."""

from __future__ import annotations

from ..config import settings
from .base import Reasoner
from .deterministic import DeterministicReasoner


def get_reasoner() -> Reasoner:
    if settings.reasoner == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("REASONER=openai but OPENAI_API_KEY is not set.")
        from .openai_reasoner import OpenAIReasoner

        return OpenAIReasoner(settings.openai_api_key, settings.openai_model)
    return DeterministicReasoner()
