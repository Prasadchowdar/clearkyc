"""Identity verification engine — the core IP of ClearKYC.

This is pure, deterministic logic (no LLM), which makes it fast, free, and
unit-testable. It is responsible for catching the single biggest cause of real
KYC rejections: name/identity mismatches across PAN, GST, bank, and
registration documents (~40% of rejections per industry data).

Three responsibilities:
  1. normalize_name  — canonicalize Indian legal names so cosmetic differences
                       ("Pvt. Ltd." vs "Private Limited") don't trigger rejects.
  2. validators      — PAN / GSTIN (with checksum) / IFSC format checks.
  3. build_findings  — turn a set of extracted documents into structured
                       RiskFindings the decision engine can reason over.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

# --------------------------------------------------------------------------- #
# Extracted document container (output of the extractor layer)                #
# --------------------------------------------------------------------------- #


@dataclass
class ExtractedDoc:
    doc_id: str
    doc_type: str  # PAN | GST | BANK | REG | WEBSITE
    fields: dict[str, str]  # e.g. {"legal_name": "...", "pan": "..."}
    quality_score: float = 1.0
    raw: dict[str, Any] | None = field(default=None)


# --------------------------------------------------------------------------- #
# Name normalization                                                          #
# --------------------------------------------------------------------------- #

# Common Indian business-name abbreviations -> canonical form.
_ABBREV = {
    "PVT": "PRIVATE",
    "PVTLTD": "PRIVATE LIMITED",
    "LTD": "LIMITED",
    "LLP": "LLP",
    "LLC": "LLC",
    "CO": "COMPANY",
    "CORP": "CORPORATION",
    "INC": "INCORPORATED",
    "ENT": "ENTERPRISES",
    "ENTPR": "ENTERPRISES",
    "INDS": "INDUSTRIES",
    "MFG": "MANUFACTURING",
    "TECH": "TECHNOLOGIES",
}

# Tokens that carry no identifying signal and should be ignored when comparing.
_NOISE = {"M", "S", "MS", "THE"}  # "M/s", "M/S", "The"


def normalize_name(raw: str) -> str:
    """Return an upper-cased, punctuation-stripped, abbreviation-expanded name."""
    if not raw:
        return ""
    s = raw.upper()
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)  # drop dots, slashes, commas, etc.
    tokens = [t for t in s.split() if t]
    expanded: list[str] = []
    for t in tokens:
        if t in _NOISE:
            continue
        expanded.append(_ABBREV.get(t, t))
    # Re-split because some abbreviations expand to multiple words.
    return " ".join(" ".join(expanded).split())


def name_match_score(a: str, b: str) -> float:
    """Similarity in [0, 1]. 1.0 == identical after normalization."""
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    # token_set_ratio is robust to word order and extra/missing tokens.
    return round(fuzz.token_set_ratio(na, nb) / 100.0, 4)


# --------------------------------------------------------------------------- #
# Format validators                                                           #
# --------------------------------------------------------------------------- #

_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
_GSTIN_RE = re.compile(
    r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$"
)
_GST_CODE = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def valid_pan(s: str | None) -> bool:
    return bool(s) and bool(_PAN_RE.match(s.strip().upper()))


def valid_ifsc(s: str | None) -> bool:
    return bool(s) and bool(_IFSC_RE.match(s.strip().upper()))


def _gstin_check_digit(first14: str) -> str:
    """GSTN check-digit algorithm (mod-36, alternating factor)."""
    factor = 2
    total = 0
    for ch in reversed(first14):
        digit = factor * _GST_CODE.index(ch)
        factor = 1 if factor == 2 else 2
        total += (digit // 36) + (digit % 36)
    return _GST_CODE[(36 - (total % 36)) % 36]


def valid_gstin(s: str | None) -> bool:
    """Format AND checksum validation."""
    if not s:
        return False
    g = s.strip().upper()
    if not _GSTIN_RE.match(g):
        return False
    try:
        return _gstin_check_digit(g[:14]) == g[14]
    except ValueError:
        return False


# --------------------------------------------------------------------------- #
# Finding construction                                                        #
# --------------------------------------------------------------------------- #

NAME_MATCH_HARD = 0.60   # below this: HIGH severity (likely different entity)
NAME_MATCH_SOFT = 0.90   # below this: MEDIUM severity (cosmetic but flagged)
QUALITY_MIN = 0.55       # below this: document too poor to trust

# Per-doc-type, the field that holds the entity/person name.
_NAME_FIELD = {
    "PAN": "legal_name",
    "GST": "legal_name",
    "BANK": "account_name",
    "REG": "legal_name",
}


def _doc_name(doc: ExtractedDoc) -> str | None:
    return doc.fields.get(_NAME_FIELD.get(doc.doc_type, "legal_name"))


def build_findings(docs: list[ExtractedDoc]) -> list[dict]:
    """Return structured findings (dicts ready to persist as RiskFinding)."""
    findings: list[dict] = []

    # 1) Document quality
    for d in docs:
        if d.quality_score < QUALITY_MIN:
            findings.append(
                {
                    "code": "LOW_QUALITY",
                    "rule": "DOC_QUALITY_POLICY",
                    "severity": "MEDIUM",
                    "detail": (
                        f"{d.doc_type} document is low quality "
                        f"(score {d.quality_score:.2f}); fields may be unreliable."
                    ),
                    "evidence": {"doc_id": d.doc_id, "quality_score": d.quality_score},
                }
            )

    # 2) Format / checksum validation
    for d in docs:
        pan = d.fields.get("pan")
        if pan is not None and not valid_pan(pan):
            findings.append(_fmt_finding("INVALID_PAN", "PAN_FORMAT", d.doc_id, pan))
        gstin = d.fields.get("gstin")
        if gstin is not None and not valid_gstin(gstin):
            findings.append(_fmt_finding("INVALID_GSTIN", "GSTIN_CHECKSUM", d.doc_id, gstin))
        ifsc = d.fields.get("ifsc")
        if ifsc is not None and not valid_ifsc(ifsc):
            findings.append(_fmt_finding("INVALID_IFSC", "IFSC_FORMAT", d.doc_id, ifsc))

    # 3) Cross-document name matching (the headline check).
    # Reference name = PAN's name if present (PAN is the legal anchor in India),
    # else the registration certificate, else the first available.
    named = [(d, _doc_name(d)) for d in docs if _doc_name(d)]
    ref = next((p for p in named if p[0].doc_type == "PAN"), None)
    if ref is None:
        ref = next((p for p in named if p[0].doc_type == "REG"), None)
    if ref is None and named:
        ref = named[0]

    if ref is not None:
        ref_doc, ref_name = ref
        for d, name in named:
            if d.doc_id == ref_doc.doc_id:
                continue
            score = name_match_score(ref_name, name)
            if score >= NAME_MATCH_SOFT:
                continue
            severity = "HIGH" if score < NAME_MATCH_HARD else "MEDIUM"
            findings.append(
                {
                    "code": "NAME_MISMATCH",
                    "rule": "RBI_NAME_CONSISTENCY",
                    "severity": severity,
                    "detail": (
                        f"Name on {d.doc_type} ('{name}') does not match "
                        f"{ref_doc.doc_type} ('{ref_name}') "
                        f"[match {score:.0%}]."
                    ),
                    "evidence": {
                        "reference_doc": ref_doc.doc_type,
                        "reference_name": ref_name,
                        "compared_doc": d.doc_type,
                        "compared_name": name,
                        "match_score": score,
                    },
                }
            )

    return findings


def _fmt_finding(code: str, rule: str, doc_id: str, value: str) -> dict:
    return {
        "code": code,
        "rule": rule,
        "severity": "HIGH",
        "detail": f"{code.replace('INVALID_', '')} value '{value}' is invalid.",
        "evidence": {"doc_id": doc_id, "value": value},
    }
