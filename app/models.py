"""ORM models — the domain contracts.

Design notes (these survive a technical grill):
- Every Decision.reason references a finding/rule code, so explainability is
  STRUCTURAL, not "ask the LLM to explain."
- AuditEvent is append-only and immutable: the code never updates or deletes a
  row. This is the tamper-evident decision trail an RBI audit requires.
- ExtractedField / RiskFinding tables are created now but populated starting in
  Phase 1 (vision extraction + cross-doc verification).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Embedding dimension. Matches OpenAI text-embedding-3-small and the mock
# embedder, so the column width is provider-independent.
EMBED_DIM = 1536


def _uuid() -> str:
    return str(uuid.uuid4())


class MerchantCase(Base):
    __tablename__ = "merchant_cases"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    merchant_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(16))  # ONBOARD | RE_KYC | HOLD
    status: Mapped[str] = mapped_column(String(16), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["Decision"]] = relationship(
        back_populates="case",
        cascade="all, delete-orphan",
        order_by="Decision.created_at",
    )


class Document(Base):
    __tablename__ = "documents"

    doc_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("merchant_cases.case_id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(16))  # PAN | GST | BANK | REG | WEBSITE
    file_ref: Mapped[str] = mapped_column(String(512))
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case: Mapped["MerchantCase"] = relationship(back_populates="documents")


class Decision(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("merchant_cases.case_id", ondelete="CASCADE"), index=True
    )
    verdict: Mapped[str] = mapped_column(String(16))  # APPROVE | NEEDS_FIX | REJECT
    confidence: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)
    required_actions: Mapped[list] = mapped_column(JSONB, default=list)
    drafted_message: Mapped[str] = mapped_column(Text, default="")
    # Guardrail: low-confidence / REJECT verdicts route to a human before action.
    human_status: Mapped[str] = mapped_column(String(16), default="PENDING")
    engine_version: Mapped[str] = mapped_column(String(32), default="phase0-stub")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    case: Mapped["MerchantCase"] = relationship(back_populates="decisions")


class ExtractedField(Base):
    """A single field pulled from a document by the extractor (Phase 1)."""

    __tablename__ = "extracted_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doc_id: Mapped[str] = mapped_column(
        ForeignKey("documents.doc_id", ondelete="CASCADE"), index=True
    )
    field: Mapped[str] = mapped_column(String(32))  # legal_name, pan, gstin, ifsc...
    value_raw: Mapped[str] = mapped_column(Text, default="")
    value_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RiskFinding(Base):
    """A defect/risk detected during verification (Phase 1).

    Decisions reference these by code, making explainability structural.
    """

    __tablename__ = "risk_findings"

    finding_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("merchant_cases.case_id", ondelete="CASCADE"), index=True
    )
    code: Mapped[str] = mapped_column(String(48))  # NAME_MISMATCH, INVALID_PAN ...
    rule: Mapped[str] = mapped_column(String(48))  # grounding rule id
    severity: Mapped[str] = mapped_column(String(16))  # LOW | MEDIUM | HIGH
    detail: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Rule(Base):
    """A compliance rule in the knowledge base (Phase 2 RAG corpus).

    `embedding` is a pgvector column used for semantic retrieval. The texts are
    representative summaries of real obligations (RBI PA Master Directions, PMLA
    KYC norms, document/format standards) with their source cited — not verbatim
    legal text.
    """

    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(String(48), primary_key=True)
    source: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBED_DIM), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditEvent(Base):
    """Append-only. Never updated or deleted."""

    __tablename__ = "audit_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(String(36), index=True)
    actor: Mapped[str] = mapped_column(String(16))  # SYSTEM | AGENT | HUMAN
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
