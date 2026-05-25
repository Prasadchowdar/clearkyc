"""Extractor interface + the structured fields we ask each document type for.

Keeping this as a Protocol means the rest of the system depends on the
*contract*, not on OpenAI. Swapping providers (or running the mock) changes one
env var, nothing else. That decoupling is the "I route cheap-vs-strong models"
story in architecture terms.
"""

from __future__ import annotations

from typing import Protocol

from ..matching import ExtractedDoc

# Fields requested per document type. Drives both the OpenAI prompt and the
# mock's expected schema, so they can never silently diverge.
FIELDS_BY_TYPE: dict[str, list[str]] = {
    "PAN": ["legal_name", "pan", "father_name", "dob"],
    "GST": ["legal_name", "gstin", "trade_name", "address"],
    "BANK": ["account_name", "account_number", "ifsc", "bank_name"],
    "REG": ["legal_name", "registration_number", "entity_type"],
    "WEBSITE": ["business_name", "has_contact", "has_pricing", "has_policies"],
}


class DocumentExtractor(Protocol):
    """Reads one document and returns structured fields + a quality score."""

    def extract(self, doc_id: str, doc_type: str, file_ref: str) -> ExtractedDoc:
        ...
