"""Unit tests for the deterministic reasoner (citations + verdict logic)."""

from app.reasoner.deterministic import DeterministicReasoner

KB = {
    "RBI_NAME_CONSISTENCY": {"source": "RBI MD — KYC", "snippet": "names must match"},
    "RAZORPAY_KYC_MINIMUM": {"source": "PA onboarding", "snippet": "min docs"},
}


def test_attaches_citation_and_flags_mismatch():
    findings = [
        {
            "code": "NAME_MISMATCH",
            "rule": "RBI_NAME_CONSISTENCY",
            "severity": "HIGH",
            "detail": "bank vs pan",
            "evidence": {},
        }
    ]
    d = DeterministicReasoner().reason(missing=[], findings=findings, kb=KB)
    assert d["verdict"] == "NEEDS_FIX"
    assert d["engine_version"] == "phase2-rules+rag"
    assert d["reasons"][0]["citation"]["rule_id"] == "RBI_NAME_CONSISTENCY"
    assert d["reasons"][0]["citation"]["source"] == "RBI MD — KYC"


def test_missing_docs_cite_minimum_rule():
    d = DeterministicReasoner().reason(missing=["BANK"], findings=[], kb=KB)
    assert d["verdict"] == "NEEDS_FIX"
    assert d["reasons"][0]["citation"]["rule_id"] == "RAZORPAY_KYC_MINIMUM"


def test_clean_case_approves():
    d = DeterministicReasoner().reason(missing=[], findings=[], kb=KB)
    assert d["verdict"] == "APPROVE"
