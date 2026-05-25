"""Unit tests for the deterministic guardrails (the safety net over any reasoner)."""

from app.decision import enforce_guardrails, has_fatal_finding

_NAME_MISMATCH = {"code": "NAME_MISMATCH", "rule": "RBI_NAME_CONSISTENCY", "severity": "HIGH"}
_UNSUPPORTED = {"code": "UNSUPPORTED_CATEGORY", "rule": "CATEGORY_SUPPORT", "severity": "HIGH"}


def test_reject_downgraded_when_all_fixable():
    # The exact LLM failure we observed: REJECT for a fixable name mismatch.
    result = {"verdict": "REJECT", "confidence": 1.0}
    out, overrides = enforce_guardrails(result, [_NAME_MISMATCH])
    assert out["verdict"] == "NEEDS_FIX"
    assert "REJECT_WITHOUT_FATAL" in overrides


def test_reject_kept_when_fatal_finding_present():
    result = {"verdict": "REJECT", "confidence": 0.95}
    out, overrides = enforce_guardrails(result, [_UNSUPPORTED])
    assert out["verdict"] == "REJECT"
    assert overrides == []


def test_approve_downgraded_over_high_finding():
    result = {"verdict": "APPROVE", "confidence": 0.99}
    out, overrides = enforce_guardrails(result, [_NAME_MISMATCH])
    assert out["verdict"] == "NEEDS_FIX"
    assert "APPROVE_OVER_HIGH" in overrides


def test_has_fatal_finding():
    assert not has_fatal_finding([_NAME_MISMATCH])
    assert has_fatal_finding([_UNSUPPORTED])
