"""Deterministic mock extractor.

In mock mode a "document" is simply a JSON file whose contents are the
already-extracted fields. This lets the whole pipeline + eval harness run with
zero API cost and perfectly reproducible results.

Expected JSON shape (file_ref points to this file):
    {
        "fields": {"legal_name": "ACME PRIVATE LIMITED", "pan": "ABCDE1234F"},
        "quality_score": 0.97
    }
"""

from __future__ import annotations

import json
from pathlib import Path

from ..matching import ExtractedDoc


class MockDocumentExtractor:
    def extract(self, doc_id: str, doc_type: str, file_ref: str) -> ExtractedDoc:
        path = Path(file_ref)
        if path.exists():
            data = json.loads(path.read_text())
            fields = data.get("fields", {})
            quality = float(data.get("quality_score", 1.0))
        else:
            # No fixture file -> empty extraction (treated as missing fields).
            fields, quality = {}, 0.0
        return ExtractedDoc(
            doc_id=doc_id,
            doc_type=doc_type,
            fields={k: str(v) for k, v in fields.items()},
            quality_score=quality,
            raw={"source": "mock", "file_ref": file_ref},
        )
