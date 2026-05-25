"""Reasoner interface.

A reasoner turns (missing docs, findings, grounding rulebook) into a structured
decision. `kb` maps rule_id -> {"source", "snippet"} for the rules retrieved via
RAG plus any rule directly referenced by a finding.

The output contract is identical across phases (verdict, confidence, reasons,
required_actions, drafted_message, engine_version). Phase 2 adds a `citation`
to each reason so every verdict is grounded in a named rule + source.
"""

from __future__ import annotations

from typing import Protocol


class Reasoner(Protocol):
    def reason(
        self,
        *,
        missing: list[str],
        findings: list[dict],
        kb: dict[str, dict],
    ) -> dict: ...
