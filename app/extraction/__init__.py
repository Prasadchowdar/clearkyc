"""Document extraction layer (provider-agnostic)."""

from .base import DocumentExtractor
from .factory import get_extractor

__all__ = ["DocumentExtractor", "get_extractor"]
