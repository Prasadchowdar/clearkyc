"""Compliance rule corpus + idempotent seeder.

IMPORTANT: these texts are *representative summaries* of real obligations with
their source cited — they are NOT verbatim legal text and must not be quoted as
law. They exist to ground the reasoner's explanations in the actual basis for
each decision (the thing Razorpay's generic rejection emails never do).

Each rule_id intentionally matches the `rule` value emitted by the verification
engine (app/matching.py) so findings link directly to their grounding rule, in
addition to semantic RAG retrieval.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import models

RULES: list[dict] = [
    {
        "rule_id": "RBI_NAME_CONSISTENCY",
        "source": "RBI Master Direction on Payment Aggregators & PGs — KYC identity consistency",
        "text": (
            "The legal name of the merchant entity must be consistent across PAN, "
            "GST, bank account, and registration documents. Cosmetic variations of "
            "statutory suffixes (e.g. 'Pvt. Ltd.' vs 'Private Limited') are "
            "acceptable. Substantively different names indicate a possible identity "
            "mismatch and must be corrected, or supported by a name-change affidavit, "
            "before activation."
        ),
    },
    {
        "rule_id": "PMLA_KYC",
        "source": "Prevention of Money Laundering Act, 2002 — customer due diligence",
        "text": (
            "Regulated entities must verify and record the identity of every customer "
            "before establishing an account-based relationship. Identity verification "
            "must rely on reliable, independent source documents. Inability to verify "
            "identity is grounds to refuse onboarding."
        ),
    },
    {
        "rule_id": "RAZORPAY_KYC_MINIMUM",
        "source": "Payment Aggregator onboarding — minimum KYC document set",
        "text": (
            "At minimum, merchant onboarding requires proof of PAN and a valid bank "
            "account. GST and business registration are required for applicable entity "
            "types. Activation cannot proceed until the minimum document set is present."
        ),
    },
    {
        "rule_id": "PAN_FORMAT",
        "source": "Income Tax Department — PAN format specification",
        "text": (
            "A PAN is a 10-character identifier: five letters, four digits, and a "
            "trailing letter (e.g. ABCDE1234F). Values not matching this pattern are "
            "invalid and cannot be accepted as identity proof."
        ),
    },
    {
        "rule_id": "GSTIN_CHECKSUM",
        "source": "GST Network — GSTIN structure and check digit",
        "text": (
            "A GSTIN is a 15-character identifier encoding state code, the entity PAN, "
            "an entity number, a default 'Z', and a check digit computed by a mod-36 "
            "algorithm. A GSTIN that fails the checksum is invalid."
        ),
    },
    {
        "rule_id": "IFSC_FORMAT",
        "source": "RBI — IFSC format specification",
        "text": (
            "An IFSC is an 11-character bank-branch code: four letters identifying the "
            "bank, a mandatory '0', and a six-character branch identifier. Bank proof "
            "with an invalid IFSC cannot be used to verify the settlement account."
        ),
    },
    {
        "rule_id": "DOC_QUALITY_POLICY",
        "source": "KYC document submission standards",
        "text": (
            "Submitted documents must be legible, complete, unedited, in an accepted "
            "format (PDF/PNG/JPG), and under the size limit. Blurred or partial scans "
            "prevent reliable field extraction and must be re-submitted."
        ),
    },
    {
        "rule_id": "CATEGORY_SUPPORT",
        "source": "Payment Aggregator — supported business categories / MCC policy",
        "text": (
            "Only businesses in supported categories may be onboarded. Restricted or "
            "prohibited categories (per RBI and card-network rules) are rejected at "
            "KYC regardless of document quality."
        ),
    },
    {
        "rule_id": "RE_KYC_PERIODIC",
        "source": "RBI — periodic re-KYC / dormant account review",
        "text": (
            "KYC must be periodically refreshed based on the merchant's risk "
            "classification. Dormant accounts (typically no activity for 12 months) "
            "may be paused pending fresh verification."
        ),
    },
]


def seed_rules(db: Session, embedder) -> int:
    """Embed and insert rules if the table is empty. Returns rows inserted."""
    if db.query(models.Rule).count() > 0:
        return 0
    vectors = embedder.embed_many([r["text"] for r in RULES])
    for r, vec in zip(RULES, vectors):
        db.add(
            models.Rule(
                rule_id=r["rule_id"], source=r["source"], text=r["text"], embedding=vec
            )
        )
    db.commit()
    return len(RULES)
