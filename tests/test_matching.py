"""Unit tests for the identity verification engine.

These are deterministic and require no DB or API. They are the foundation the
Phase 3 eval harness will build on.
"""

from app.matching import (
    ExtractedDoc,
    _gstin_check_digit,
    build_findings,
    name_match_score,
    normalize_name,
    valid_gstin,
    valid_ifsc,
    valid_pan,
)


# --- normalization --------------------------------------------------------- #

def test_normalize_expands_entity_suffixes():
    assert normalize_name("ACME Pvt. Ltd.") == "ACME PRIVATE LIMITED"
    assert normalize_name("Acme Private Limited") == "ACME PRIVATE LIMITED"
    assert normalize_name("M/s Acme Pvt Ltd") == "ACME PRIVATE LIMITED"


def test_normalize_handles_ampersand_and_punctuation():
    assert normalize_name("Tata & Sons, Inc.") == "TATA AND SONS INCORPORATED"


# --- the headline check: cosmetic differences must NOT count as mismatches -- #

def test_cosmetic_difference_is_full_match():
    # This is the ~40%-of-rejections case Razorpay gets wrong.
    assert name_match_score("ACME PRIVATE LIMITED", "Acme Pvt. Ltd.") == 1.0


def test_genuinely_different_names_score_low():
    assert name_match_score("ACME PRIVATE LIMITED", "Globex Corporation") < 0.5


def test_empty_name_scores_zero():
    assert name_match_score("", "Acme") == 0.0


# --- validators ------------------------------------------------------------ #

def test_valid_pan():
    assert valid_pan("ABCDE1234F")
    assert not valid_pan("ABCD1234F")   # too short
    assert not valid_pan("ABCDE12345")  # wrong trailing type
    assert not valid_pan(None)


def test_valid_ifsc():
    assert valid_ifsc("HDFC0001234")
    assert not valid_ifsc("HDFC1001234")  # 5th char must be 0
    assert not valid_ifsc("HDF0001234")   # too short


def test_gstin_checksum():
    first14 = "27AAPFU0939F1Z"
    cd = _gstin_check_digit(first14)
    assert valid_gstin(first14 + cd)             # correct check digit passes
    wrong = "A" if cd != "A" else "B"
    assert not valid_gstin(first14 + wrong)      # wrong check digit fails
    assert not valid_gstin("NONSENSE")           # bad format fails


# --- finding construction -------------------------------------------------- #

def _doc(doc_type, **fields):
    q = fields.pop("quality_score", 1.0)
    return ExtractedDoc(doc_id=doc_type.lower(), doc_type=doc_type, fields=fields, quality_score=q)


def test_clean_case_has_no_findings():
    docs = [
        _doc("PAN", legal_name="ACME PRIVATE LIMITED", pan="ABCDE1234F"),
        _doc("BANK", account_name="Acme Pvt Ltd", ifsc="HDFC0001234"),
    ]
    assert build_findings(docs) == []


def test_name_mismatch_is_flagged_against_pan():
    docs = [
        _doc("PAN", legal_name="ACME PRIVATE LIMITED", pan="ABCDE1234F"),
        _doc("BANK", account_name="Globex Corporation", ifsc="HDFC0001234"),
    ]
    findings = build_findings(docs)
    codes = {f["code"] for f in findings}
    assert "NAME_MISMATCH" in codes
    nm = next(f for f in findings if f["code"] == "NAME_MISMATCH")
    assert nm["severity"] == "HIGH"
    assert nm["evidence"]["reference_doc"] == "PAN"


def test_invalid_pan_is_flagged():
    docs = [_doc("PAN", legal_name="ACME", pan="BADPAN")]
    codes = {f["code"] for f in build_findings(docs)}
    assert "INVALID_PAN" in codes


def test_low_quality_is_flagged():
    docs = [_doc("PAN", legal_name="ACME", pan="ABCDE1234F", quality_score=0.2)]
    codes = {f["code"] for f in build_findings(docs)}
    assert "LOW_QUALITY" in codes
