"""Prove the REAL OpenAI vision extractor works on synthetic doc images, and
that the matching engine produces the right verdict on the extracted fields.

Requires: OPENAI_API_KEY in the environment (or a gitignored .env).
Run:
    python scripts/gen_images.py            # once, to create the images
    EXTRACTOR=openai python scripts/test_openai_extractor.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("EXTRACTOR", "openai")

from app.extraction import get_extractor  # noqa: E402
from app.matching import build_findings  # noqa: E402

IMG = Path(__file__).resolve().parent.parent / "fixtures" / "images"


def main() -> None:
    extractor = get_extractor()
    pan = extractor.extract("d_pan", "PAN", str(IMG / "pan_acme.png"))
    bank = extractor.extract("d_bank", "BANK", str(IMG / "bank_acme.png"))

    print("PAN  extracted:", json.dumps(pan.fields), f"(quality {pan.quality_score})")
    print("BANK extracted:", json.dumps(bank.fields), f"(quality {bank.quality_score})")

    findings = build_findings([pan, bank])
    print("findings:", json.dumps(findings, indent=2))
    print(
        "\nEXPECTED: no NAME_MISMATCH — 'ACME PRIVATE LIMITED' and 'Acme Pvt. Ltd.' "
        "are the same entity."
    )


if __name__ == "__main__":
    main()
