"""Decision logic — Phase 1 (rule-based over structured findings).

Pure functions: given which documents are present and the RiskFindings produced
by the verification engine, derive a verdict, confidence, human-readable
reasons, required actions, and a drafted merchant message.

The OUTPUT CONTRACT is identical to Phase 0 — only the logic filling it grew up.
Phase 2 will swap this rule-based core for an agentic reasoner grounded in
RBI/PMLA rules via RAG, behind the same contract.
"""

from __future__ import annotations

ENGINE_VERSION = "phase1-rules"

# Minimum document set required to even attempt a content verdict.
REQUIRED_DOCS = {"PAN", "BANK"}

# Merchant-facing fix instructions, keyed by finding code.
_ACTION = {
    "MISSING_DOCS": "Upload the missing document(s) listed above.",
    "NAME_MISMATCH": (
        "Make the name identical across all documents — e.g. update your bank "
        "proof to match your PAN exactly — or submit a name-change affidavit."
    ),
    "INVALID_PAN": "Re-upload a clear PAN showing a valid 10-character PAN number.",
    "INVALID_GSTIN": "Re-upload a GST certificate with a valid GSTIN.",
    "INVALID_IFSC": "Provide bank proof showing a valid 11-character IFSC code.",
    "LOW_QUALITY": "Re-upload a clearer, well-lit scan (PDF/PNG/JPG, under 5 MB).",
}


# Findings a merchant can fix by correcting and resubmitting. Anything NOT in
# this set is treated as potentially fatal (e.g. an unsupported business
# category) and may justify a REJECT. Used by the symmetric guardrail below.
FIXABLE_CODES = {
    "MISSING_DOCS",
    "NAME_MISMATCH",
    "INVALID_PAN",
    "INVALID_GSTIN",
    "INVALID_IFSC",
    "LOW_QUALITY",
}


def missing_docs(present_types: set[str]) -> list[str]:
    return sorted(REQUIRED_DOCS - present_types)


def has_fatal_finding(findings: list[dict]) -> bool:
    """True if any finding is unfixable (i.e. could justify a REJECT)."""
    return any(f["code"] not in FIXABLE_CODES for f in findings)


def enforce_guardrails(result: dict, findings: list[dict]) -> tuple[dict, list[str]]:
    """Deterministic safety net applied to ANY reasoner's output.

    Two symmetric rules:
      - never APPROVE over a HIGH-severity finding   (protects compliance)
      - never REJECT when every finding is fixable    (protects the merchant)

    Returns (possibly-modified result, list of override names for the audit log).
    """
    overrides: list[str] = []

    if result["verdict"] == "APPROVE" and any(
        f["severity"] == "HIGH" for f in findings
    ):
        result["verdict"] = "NEEDS_FIX"
        result["confidence"] = min(result["confidence"], 0.90)
        overrides.append("APPROVE_OVER_HIGH")

    if result["verdict"] == "REJECT" and not has_fatal_finding(findings):
        result["verdict"] = "NEEDS_FIX"
        result["confidence"] = min(result["confidence"], 0.90)
        overrides.append("REJECT_WITHOUT_FATAL")

    return result, overrides


def compose_decision(missing: list[str], findings: list[dict]) -> dict:
    """Return a structured decision dict (keys map 1:1 to Decision columns)."""
    if missing:
        return {
            "verdict": "NEEDS_FIX",
            "confidence": 0.99,
            "reasons": [
                {
                    "code": "MISSING_DOCS",
                    "rule": "RAZORPAY_KYC_MINIMUM",
                    "severity": "HIGH",
                    "detail": f"Required documents not submitted: {', '.join(missing)}.",
                }
            ],
            "required_actions": [f"Upload your {d} document." for d in missing],
            "drafted_message": (
                "Hi! Your KYC is almost ready — we just need a couple more "
                f"documents: {', '.join(missing)}. Once uploaded, verification "
                "usually completes within a day."
            ),
            "engine_version": ENGINE_VERSION,
        }

    has_high = any(f["severity"] == "HIGH" for f in findings)
    has_medium = any(f["severity"] == "MEDIUM" for f in findings)

    if has_high or has_medium:
        verdict = "NEEDS_FIX"
        confidence = 0.92 if has_high else 0.75
        reasons = [
            {k: f[k] for k in ("code", "rule", "severity", "detail")} for f in findings
        ]
        # De-duplicated, ordered actions.
        seen: set[str] = set()
        actions: list[str] = []
        for f in findings:
            act = _ACTION.get(f["code"])
            if act and act not in seen:
                seen.add(act)
                actions.append(act)
        message = _draft_needs_fix(findings)
        return {
            "verdict": verdict,
            "confidence": confidence,
            "reasons": reasons,
            "required_actions": actions,
            "drafted_message": message,
            "engine_version": ENGINE_VERSION,
        }

    # Clean: required docs present, no HIGH/MEDIUM findings.
    return {
        "verdict": "APPROVE",
        "confidence": 0.90,
        "reasons": [
            {
                "code": "VERIFIED",
                "rule": "RBI_NAME_CONSISTENCY",
                "severity": "LOW",
                "detail": "Documents present, names consistent, formats valid.",
            }
        ],
        "required_actions": [],
        "drafted_message": (
            "Hi! Your documents check out and your KYC has cleared our automated "
            "review. You're all set."
        ),
        "engine_version": ENGINE_VERSION,
    }


def _draft_needs_fix(findings: list[dict]) -> str:
    """A specific, human message — the opposite of Razorpay's generic template."""
    issues = []
    for f in findings:
        if f["code"] == "NAME_MISMATCH":
            ev = f.get("evidence", {})
            issues.append(
                f"the name on your {ev.get('compared_doc', 'document')} doesn't "
                f"match your {ev.get('reference_doc', 'PAN')}"
            )
        elif f["code"].startswith("INVALID_"):
            issues.append(f"the {f['code'].replace('INVALID_', '')} value looks invalid")
        elif f["code"] == "LOW_QUALITY":
            issues.append("one of your scans is hard to read")
    issue_text = "; ".join(issues) if issues else "a few details need fixing"
    return (
        f"Hi! Your KYC is almost there. We found one thing to fix: {issue_text}. "
        "See the steps below — most merchants resolve this in a few minutes, and "
        "then we re-check automatically."
    )
