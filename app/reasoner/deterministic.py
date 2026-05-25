"""Deterministic reasoner (free, offline).

Reuses the audited rule-based decision logic from Phase 1, then grounds each
reason with a citation from the retrieved knowledge base. This keeps evals fast
and reproducible while still demonstrating RAG-grounded explanations.
"""

from __future__ import annotations

from ..decision import compose_decision

ENGINE_VERSION = "phase2-rules+rag"


class DeterministicReasoner:
    def reason(
        self, *, missing: list[str], findings: list[dict], kb: dict[str, dict]
    ) -> dict:
        decision = compose_decision(missing, findings)
        for reason in decision["reasons"]:
            rid = reason.get("rule")
            if rid in kb:
                reason["citation"] = {
                    "rule_id": rid,
                    "source": kb[rid]["source"],
                    "snippet": kb[rid]["snippet"],
                }
        decision["engine_version"] = ENGINE_VERSION
        return decision
