"""Pydantic schemas — the API data contracts (request/response shapes)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

CaseType = Literal["ONBOARD", "RE_KYC", "HOLD"]
DocType = Literal["PAN", "GST", "BANK", "REG", "WEBSITE"]
Verdict = Literal["APPROVE", "NEEDS_FIX", "REJECT"]


class CaseCreate(BaseModel):
    merchant_id: str
    type: CaseType = "ONBOARD"


class DocumentCreate(BaseModel):
    type: DocType
    file_ref: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    doc_id: str
    type: str
    file_ref: str
    quality_score: float | None = None
    created_at: datetime


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision_id: str
    verdict: str
    confidence: float
    reasons: list = []
    required_actions: list = []
    drafted_message: str
    human_status: str
    engine_version: str
    created_at: datetime


class ReviewRequest(BaseModel):
    action: Literal["APPROVE", "OVERRIDE"]
    reviewer: str = "reviewer"
    note: str = ""


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    actor: str
    action: str
    payload: dict = {}
    ts: datetime


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    finding_id: str
    code: str
    rule: str
    severity: str
    detail: str
    evidence: dict = {}
    created_at: datetime


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    merchant_id: str
    type: str
    status: str
    created_at: datetime
    documents: list[DocumentOut] = []
    decisions: list[DecisionOut] = []
