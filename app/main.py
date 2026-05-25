"""ClearKYC API — Phase 1 (extraction + verification).

Endpoints:
    GET  /health
    POST /cases                       create a merchant case
    POST /cases/{case_id}/documents   attach a document
    POST /cases/{case_id}/decide      extract -> verify -> decide -> persist
    GET  /cases/{case_id}             fetch case with documents + decisions
    GET  /cases/{case_id}/findings    structured risk findings for the case

Every state change writes an append-only AuditEvent.
"""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

VALID_DOC_TYPES = {"PAN", "GST", "BANK", "REG", "WEBSITE"}

from . import models, schemas
from .config import settings
from .db import Base, SessionLocal, engine, get_db
from .embeddings import get_embedder
from .extraction import get_extractor
from .knowledge import seed_rules
from .service import evaluate_case

# Preset demo scenarios -> (doc_type, fixture basename). The file extension is
# chosen at request time: real image (.png) in OpenAI mode, JSON in mock mode.
DEMO_SCENARIOS: dict[str, list[tuple[str, str]]] = {
    "clean": [("PAN", "clean_pan"), ("BANK", "clean_bank")],
    "mismatch": [("PAN", "mismatch_pan"), ("BANK", "mismatch_bank")],
    "missing": [("PAN", "clean_pan")],
}


def _demo_file_ref(basename: str) -> str:
    """Real document image when using the vision extractor, else a JSON fixture."""
    if settings.extractor == "openai":
        return f"{settings.fixtures_dir}/images/{basename}.png"
    return f"{settings.fixtures_dir}/{basename}.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables, then seed the compliance KB if empty (idempotent).
    # With the default mock embedder this is free and offline.
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        inserted = seed_rules(db, get_embedder())
        if inserted:
            print(f"[startup] seeded {inserted} compliance rules")
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


def _log_audit(db: Session, case_id: str, actor: str, action: str, payload: dict) -> None:
    db.add(
        models.AuditEvent(case_id=case_id, actor=actor, action=action, payload=payload)
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.post("/cases", response_model=schemas.CaseOut, status_code=201)
def create_case(body: schemas.CaseCreate, db: Session = Depends(get_db)):
    case = models.MerchantCase(merchant_id=body.merchant_id, type=body.type)
    db.add(case)
    db.flush()  # populate case_id
    _log_audit(db, case.case_id, "SYSTEM", "CASE_CREATED", {"type": body.type})
    db.commit()
    db.refresh(case)
    return case


@app.post(
    "/cases/{case_id}/documents",
    response_model=schemas.DocumentOut,
    status_code=201,
)
def add_document(
    case_id: str, body: schemas.DocumentCreate, db: Session = Depends(get_db)
):
    case = db.get(models.MerchantCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")

    doc = models.Document(case_id=case_id, type=body.type, file_ref=body.file_ref)
    db.add(doc)
    db.flush()
    _log_audit(
        db, case_id, "SYSTEM", "DOCUMENT_ADDED", {"doc_id": doc.doc_id, "type": body.type}
    )
    db.commit()
    db.refresh(doc)
    return doc


@app.post(
    "/cases/{case_id}/documents/upload",
    response_model=schemas.DocumentOut,
    status_code=201,
)
async def upload_document(
    case_id: str,
    type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a real document image (PAN/BANK/GST/REG). Stored on a writable
    volume; the vision extractor reads it on /decide."""
    case = db.get(models.MerchantCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    doc_type = type.upper()
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"invalid document type '{type}'")

    ext = Path(file.filename or "").suffix.lower() or ".png"
    doc = models.Document(case_id=case_id, type=doc_type, file_ref="")
    db.add(doc)
    db.flush()  # get doc_id for the filename

    dest = Path(settings.uploads_dir) / f"{doc.doc_id}{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(await file.read())
    doc.file_ref = str(dest)

    _log_audit(
        db,
        case_id,
        "SYSTEM",
        "DOCUMENT_UPLOADED",
        {"doc_id": doc.doc_id, "type": doc_type, "filename": file.filename},
    )
    db.commit()
    db.refresh(doc)
    return doc


@app.post("/cases/{case_id}/decide", response_model=schemas.DecisionOut)
def decide(case_id: str, db: Session = Depends(get_db)):
    case = db.get(models.MerchantCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    # Pipeline: extract -> verify -> decide -> persist (extractor chosen by env).
    return evaluate_case(db, case, get_extractor())


@app.get("/cases/{case_id}", response_model=schemas.CaseOut)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(models.MerchantCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return case


@app.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    """The seeded compliance knowledge base (proof the RAG corpus exists)."""
    rules = db.query(models.Rule).order_by(models.Rule.rule_id).all()
    return {
        "count": len(rules),
        "rules": [{"rule_id": r.rule_id, "source": r.source} for r in rules],
    }


@app.get("/cases/{case_id}/findings", response_model=list[schemas.FindingOut])
def get_findings(case_id: str, db: Session = Depends(get_db)):
    case = db.get(models.MerchantCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="case not found")
    return (
        db.query(models.RiskFinding)
        .filter(models.RiskFinding.case_id == case_id)
        .order_by(models.RiskFinding.created_at)
        .all()
    )


@app.get("/cases/{case_id}/audit", response_model=list[schemas.AuditOut])
def get_audit(case_id: str, db: Session = Depends(get_db)):
    """The append-only, audit-grade trail of everything that happened."""
    return (
        db.query(models.AuditEvent)
        .filter(models.AuditEvent.case_id == case_id)
        .order_by(models.AuditEvent.ts)
        .all()
    )


@app.post("/decisions/{decision_id}/review", response_model=schemas.DecisionOut)
def review_decision(
    decision_id: str, body: schemas.ReviewRequest, db: Session = Depends(get_db)
):
    """Human-in-the-loop action on a decision (the HITL guardrail in practice)."""
    decision = db.get(models.Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="decision not found")
    decision.human_status = "APPROVED" if body.action == "APPROVE" else "OVERRIDDEN"
    _log_audit(
        db,
        decision.case_id,
        "HUMAN",
        "HUMAN_REVIEW",
        {
            "decision_id": decision_id,
            "action": body.action,
            "reviewer": body.reviewer,
            "note": body.note,
        },
    )
    db.commit()
    db.refresh(decision)
    return decision


@app.post("/demo/{scenario}", response_model=schemas.CaseOut)
def run_demo(scenario: str, db: Session = Depends(get_db)):
    """One-shot demo: build a case from a preset scenario and evaluate it."""
    if scenario not in DEMO_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"unknown scenario '{scenario}'")
    case = models.MerchantCase(merchant_id=f"DEMO_{scenario.upper()}", type="ONBOARD")
    db.add(case)
    db.flush()
    _log_audit(db, case.case_id, "SYSTEM", "CASE_CREATED", {"scenario": scenario})
    for doc_type, basename in DEMO_SCENARIOS[scenario]:
        db.add(
            models.Document(
                case_id=case.case_id,
                type=doc_type,
                file_ref=_demo_file_ref(basename),
            )
        )
    db.commit()
    evaluate_case(db, case, get_extractor())
    db.refresh(case)
    return case


# Reviewer console (single static page, no build step). Mounted last so it does
# not shadow the API routes above.
_STATIC = Path(__file__).parent / "static"
app.mount("/ui", StaticFiles(directory=str(_STATIC), html=True), name="ui")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/ui/")
