"""Generate synthetic KYC document images for the REAL (OpenAI vision) demo.

NOT real documents — just legible cards with controllable fields, so we can
prove genuine end-to-end vision extraction without using anyone's real PAN/bank
data. Produces both the clean pair (same entity, cosmetic name difference) and
the mismatch pair (different entities).

Usage:  python scripts/gen_images.py   ->  fixtures/images/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "fixtures" / "images"
OUT.mkdir(parents=True, exist_ok=True)


def _font(size: int):
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def card(filename: str, title: str, lines: list[tuple[str, str]]):
    img = Image.new("RGB", (640, 380), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 632, 372], outline="navy", width=3)
    d.text((24, 24), title, fill="navy", font=_font(28))
    d.line([24, 70, 616, 70], fill="navy", width=2)
    y = 110
    for label, value in lines:
        d.text((36, y), f"{label}:", fill="black", font=_font(22))
        d.text((300, y), value, fill="black", font=_font(22))
        y += 52
    img.save(OUT / filename)
    print("wrote", OUT / filename)


if __name__ == "__main__":
    # CLEAN pair: same entity, cosmetic name difference (the 40% false-reject).
    card("clean_pan.png", "INCOME TAX DEPARTMENT - PAN",
         [("Name", "ACME PRIVATE LIMITED"), ("PAN", "ABCDE1234F")])
    card("clean_bank.png", "BANK ACCOUNT PROOF",
         [("Account Name", "Acme Pvt. Ltd."), ("IFSC", "HDFC0001234")])

    # MISMATCH pair: genuinely different names -> must be flagged.
    card("mismatch_pan.png", "INCOME TAX DEPARTMENT - PAN",
         [("Name", "ACME PRIVATE LIMITED"), ("PAN", "ABCDE1234F")])
    card("mismatch_bank.png", "BANK ACCOUNT PROOF",
         [("Account Name", "Globex Solutions"), ("IFSC", "HDFC0001234")])
