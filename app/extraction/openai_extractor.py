"""OpenAI vision document extractor.

Reads a document image (local path or http URL), sends it to a vision model,
and asks for the structured fields defined in FIELDS_BY_TYPE plus a 0-1 image
quality score. Output is constrained to JSON.

Cost note: extraction is the high-volume step, so this is the place to use a
cheaper/faster vision model. The reasoning/drafting step (Phase 2) uses a
stronger model. That split is deliberate.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from ..matching import ExtractedDoc
from .base import FIELDS_BY_TYPE


def _image_payload(file_ref: str) -> str:
    """Return an image_url value: passthrough URL, or a base64 data URI."""
    if file_ref.startswith(("http://", "https://", "data:")):
        return file_ref
    path = Path(file_ref)
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{b64}"


class OpenAIDocumentExtractor:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        from openai import OpenAI  # imported lazily so mock mode needs no SDK

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def extract(self, doc_id: str, doc_type: str, file_ref: str) -> ExtractedDoc:
        fields = FIELDS_BY_TYPE.get(doc_type, ["legal_name"])
        system = (
            "You are a meticulous KYC document reader for an Indian payment "
            "aggregator. Extract ONLY what is visibly present. If a field is not "
            "present or unreadable, set it to null. Do not guess."
        )
        user_text = (
            f"This is a {doc_type} document. Return strict JSON with keys: "
            f"{fields} plus 'quality_score' (0-1, how clear/legible the scan is). "
            "Names must be transcribed exactly as printed."
        )

        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": _image_payload(file_ref)}},
                    ],
                },
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        quality = float(data.pop("quality_score", 1.0) or 0.0)
        clean = {k: str(v) for k, v in data.items() if v not in (None, "", "null")}
        return ExtractedDoc(
            doc_id=doc_id,
            doc_type=doc_type,
            fields=clean,
            quality_score=quality,
            raw={"source": "openai", "model": self._model},
        )
