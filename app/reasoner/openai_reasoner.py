"""OpenAI reasoner — grounded, agentic decision reasoning.

Given the findings and the RAG-retrieved rules, the model produces a structured
verdict where every reason cites a specific rule_id from the provided knowledge
base. The model is instructed to ground itself ONLY in the supplied rules (no
outside law), which is what makes the output auditable.

A separate deterministic guardrail in the service layer still prevents an
APPROVE over any HIGH-severity finding — we never let the LLM be the only thing
standing between a bad doc and activation.
"""

from __future__ import annotations

import json

ENGINE_VERSION = "phase2-openai+rag"

_SYSTEM = (
    "You are a KYC compliance reasoner for an Indian payment aggregator. Decide a "
    "verdict for a merchant case using ONLY the provided findings and compliance "
    "rules. Do not invent rules or cite outside law. Every reason you give MUST "
    "cite one of the provided rule_ids.\n\n"
    "Choose EXACTLY ONE verdict:\n"
    "- APPROVE: no issues; documents are present, consistent, and valid.\n"
    "- NEEDS_FIX: there is at least one issue the merchant can correct and "
    "resubmit. A name mismatch, an invalid format, a low-quality scan, or a "
    "missing document is ALWAYS fixable -> NEEDS_FIX. This is the correct verdict "
    "for almost every problem.\n"
    "- REJECT: ONLY for fatal, unfixable problems (e.g. a prohibited/unsupported "
    "business category, or confirmed identity fraud). NEVER use REJECT for "
    "anything the merchant could correct.\n\n"
    "Confidence rubric: 0.9-1.0 only when the evidence is unambiguous; 0.7-0.9 "
    "when likely but with some uncertainty; below 0.7 when genuinely unsure.\n"
    "Be specific and merchant-friendly."
)

_VERDICTS = {"APPROVE", "NEEDS_FIX", "REJECT"}


class OpenAIReasoner:
    def __init__(self, api_key: str, model: str):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def reason(
        self, *, missing: list[str], findings: list[dict], kb: dict[str, dict]
    ) -> dict:
        rules_block = [
            {"rule_id": rid, "source": v["source"], "text": v["snippet"]}
            for rid, v in kb.items()
        ]
        user = {
            "missing_documents": missing,
            "findings": findings,
            "available_rules": rules_block,
            "instructions": (
                "Return JSON: {verdict: APPROVE|NEEDS_FIX|REJECT, confidence: 0-1, "
                "reasons: [{code, rule, severity, detail, "
                "citation: {rule_id, source, snippet}}], "
                "required_actions: [string], drafted_message: string}. "
                "If documents are missing, verdict must be NEEDS_FIX."
            ),
        }

        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": json.dumps(user)},
            ],
        )
        data = json.loads(resp.choices[0].message.content)

        # Defensive normalization (never trust raw model output).
        verdict = str(data.get("verdict", "NEEDS_FIX")).upper()
        if verdict not in _VERDICTS:
            verdict = "NEEDS_FIX"
        try:
            confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
        except (TypeError, ValueError):
            confidence = 0.5

        return {
            "verdict": verdict,
            "confidence": confidence,
            "reasons": data.get("reasons", []),
            "required_actions": data.get("required_actions", []),
            "drafted_message": str(data.get("drafted_message", "")),
            "engine_version": ENGINE_VERSION,
        }
