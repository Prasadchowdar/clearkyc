"""Case evaluation service — orchestrates the Phase 2 pipeline.

    documents
        -> extractor.extract()        (OpenAI vision or mock)
        -> persist ExtractedField rows
        -> build_findings()           (name match + validators + quality)
        -> persist RiskFinding rows
        -> retrieve_rules() [RAG]     (pgvector grounding from the KB)
        -> reasoner.reason()          (deterministic or OpenAI, cited verdict)
        -> guardrail override         (never APPROVE over a HIGH finding)
        -> persist Decision + AuditEvent (with human-gate)

Keeping this out of the HTTP layer keeps endpoints thin and the pipeline
unit-testable.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import models
from .decision import enforce_guardrails, missing_docs
from .embeddings import get_embedder
from .extraction.base import DocumentExtractor
from .matching import build_findings, normalize_name
from .rag import retrieve_rules
from .reasoner import get_reasoner

# Guardrails (mirror Phase 0).
HUMAN_REVIEW_VERDICTS = {"REJECT"}
AUTO_APPROVE_MIN_CONFIDENCE = 0.90

# Which extracted field, per doc type, should also be stored normalized.
_NAME_FIELD = {"PAN": "legal_name", "GST": "legal_name", "BANK": "account_name", "REG": "legal_name"}


def _log_audit(db: Session, case_id: str, actor: str, action: str, payload: dict) -> None:
    db.add(models.AuditEvent(case_id=case_id, actor=actor, action=action, payload=payload))


def evaluate_case(
    db: Session, case: models.MerchantCase, extractor: DocumentExtractor
) -> models.Decision:
    docs = list(case.documents)
    present_types = {d.type for d in docs}
    missing = missing_docs(present_types)

    findings: list[dict] = []
    if not missing:
        extracted = []
        for d in docs:
            ex = extractor.extract(d.doc_id, d.type, d.file_ref)
            extracted.append(ex)
            # Persist extracted fields (and normalize the name field for audit).
            d.quality_score = ex.quality_score
            for field_name, value in ex.fields.items():
                norm = (
                    normalize_name(value)
                    if field_name == _NAME_FIELD.get(d.type)
                    else None
                )
                db.add(
                    models.ExtractedField(
                        doc_id=d.doc_id,
                        field=field_name,
                        value_raw=value,
                        value_normalized=norm,
                        confidence=ex.quality_score,
                    )
                )
        findings = build_findings(extracted)
        _log_audit(
            db,
            case.case_id,
            "AGENT",
            "DOCUMENTS_EXTRACTED",
            {"docs": len(extracted), "findings": len(findings)},
        )

    # Persist findings.
    for f in findings:
        db.add(
            models.RiskFinding(
                case_id=case.case_id,
                code=f["code"],
                rule=f["rule"],
                severity=f["severity"],
                detail=f["detail"],
                evidence=f.get("evidence", {}),
            )
        )

    # ---- RAG: retrieve grounding rules, then reason over them. -------------- #
    kb, retrieved_ids = _build_rulebook(db, missing, findings)
    if retrieved_ids:
        _log_audit(
            db, case.case_id, "AGENT", "RULES_RETRIEVED", {"rules": retrieved_ids}
        )
    result = get_reasoner().reason(missing=missing, findings=findings, kb=kb)

    # Deterministic safety net over ANY reasoner's output (see decision.py):
    # never APPROVE over a HIGH finding; never REJECT a fully-fixable case.
    result, overrides = enforce_guardrails(result, findings)
    for name in overrides:
        _log_audit(
            db, case.case_id, "SYSTEM", "GUARDRAIL_OVERRIDE", {"override": name}
        )

    needs_human = (
        result["verdict"] in HUMAN_REVIEW_VERDICTS
        or result["confidence"] < AUTO_APPROVE_MIN_CONFIDENCE
    )
    human_status = "PENDING" if needs_human else "AUTO_CLEARED"

    decision = models.Decision(case_id=case.case_id, human_status=human_status, **result)
    db.add(decision)
    case.status = "DECIDED"
    db.flush()
    _log_audit(
        db,
        case.case_id,
        "AGENT",
        "DECISION_MADE",
        {
            "decision_id": decision.decision_id,
            "verdict": result["verdict"],
            "confidence": result["confidence"],
            "human_status": human_status,
            "engine_version": result["engine_version"],
        },
    )
    db.commit()
    db.refresh(decision)
    return decision


# --------------------------------------------------------------------------- #
# RAG helpers                                                                  #
# --------------------------------------------------------------------------- #

_SNIPPET_LEN = 280


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET_LEN else text[:_SNIPPET_LEN].rstrip() + "…"


def _rag_query(missing: list[str], findings: list[dict]) -> str:
    if missing:
        return "merchant KYC minimum required documents PAN bank account onboarding"
    if findings:
        return "KYC verification issues: " + "; ".join(
            f"{f['code']} {f['detail']}" for f in findings
        )
    return "merchant KYC identity verification name consistency document validity"


def _build_rulebook(
    db: Session, missing: list[str], findings: list[dict]
) -> tuple[dict[str, dict], list[str]]:
    """Return (rulebook, retrieved_ids).

    rulebook maps rule_id -> {"source", "snippet"} for the semantically
    retrieved rules PLUS any rule directly referenced by a finding (so the
    grounding is never missing the rule a finding points at).
    """
    embedder = get_embedder()
    retrieved = retrieve_rules(db, _rag_query(missing, findings), k=4, embedder=embedder)
    kb = {r.rule_id: {"source": r.source, "snippet": _snippet(r.text)} for r in retrieved}
    retrieved_ids = [r.rule_id for r in retrieved]

    needed = {f["rule"] for f in findings}
    if missing:
        needed.add("RAZORPAY_KYC_MINIMUM")
    extra = [rid for rid in needed if rid not in kb]
    if extra:
        for r in db.query(models.Rule).filter(models.Rule.rule_id.in_(extra)).all():
            kb[r.rule_id] = {"source": r.source, "snippet": _snippet(r.text)}
    return kb, retrieved_ids
