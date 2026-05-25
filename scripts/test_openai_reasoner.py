"""Prove the REAL OpenAI reasoner produces a grounded, cited decision.

Requires OPENAI_API_KEY. Run:
    EXTRACTOR=openai REASONER=openai OPENAI_API_KEY=... \
        python scripts/test_openai_reasoner.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("REASONER", "openai")

from app.reasoner import get_reasoner  # noqa: E402

# A realistic name-mismatch finding + the grounding rule it points to.
FINDINGS = [
    {
        "code": "NAME_MISMATCH",
        "rule": "RBI_NAME_CONSISTENCY",
        "severity": "HIGH",
        "detail": "Name on BANK ('Globex Solutions') does not match PAN ('ACME PRIVATE LIMITED') [match 28%].",
        "evidence": {"reference_doc": "PAN", "compared_doc": "BANK"},
    }
]
KB = {
    "RBI_NAME_CONSISTENCY": {
        "source": "RBI Master Direction on Payment Aggregators — KYC identity consistency",
        "snippet": (
            "The legal name of the merchant must be consistent across PAN, GST, bank, "
            "and registration documents. Substantively different names must be "
            "corrected or supported by an affidavit before activation."
        ),
    }
}


def main() -> None:
    decision = get_reasoner().reason(missing=[], findings=FINDINGS, kb=KB)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
