"""Eval harness — measures the decision engine against a labeled golden set.

This is the answer to "how do you know your agent is right?". It runs the SAME
decision logic the service uses (build_findings -> reasoner -> guardrails),
purely in-process (no DB/API), and reports the metrics that actually matter for
a fintech KYC system:

  - verdict accuracy
  - FALSE-APPROVE rate  -> regulatory/compliance risk (must be ~0)
  - FALSE-REJECT  rate  -> merchant churn / the trust problem we exist to fix
  - NAME_MISMATCH precision & recall -> the ~40%-of-rejections headline check

Runs the deterministic engine (the production default). The OpenAI reasoner can
be evaluated separately; it costs money and is non-deterministic, so it is not
part of the CI gate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.decision import enforce_guardrails, missing_docs  # noqa: E402
from app.knowledge import RULES  # noqa: E402
from app.matching import ExtractedDoc, build_findings  # noqa: E402
from app.reasoner.deterministic import DeterministicReasoner  # noqa: E402

GOLDEN = Path(__file__).resolve().parent / "golden.jsonl"
KB = {r["rule_id"]: {"source": r["source"], "snippet": r["text"][:280]} for r in RULES}
_REASONER = DeterministicReasoner()


def run_case(case: dict) -> tuple[str, set[str]]:
    """Return (predicted_verdict, predicted_codes) for one golden case."""
    docs = [
        ExtractedDoc(
            doc_id=f"{case['id']}_{d['type']}",
            doc_type=d["type"],
            fields={k: str(v) for k, v in d["fields"].items()},
            quality_score=float(d.get("quality_score", 1.0)),
        )
        for d in case["docs"]
    ]
    present = {d.doc_type for d in docs}
    missing = missing_docs(present)
    findings = [] if missing else build_findings(docs)
    result = _REASONER.reason(missing=missing, findings=findings, kb=KB)
    result, _ = enforce_guardrails(result, findings)

    codes = {f["code"] for f in findings}
    if missing:
        codes.add("MISSING_DOCS")
    return result["verdict"], codes


def evaluate(path: Path = GOLDEN) -> dict:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    total = len(cases)
    correct = false_approve = false_reject = 0
    nm_tp = nm_fp = nm_fn = 0
    rows = []

    for c in cases:
        pred_v, pred_codes = run_case(c)
        exp_v = c["expected_verdict"]
        exp_codes = set(c.get("expected_codes", []))

        ok = pred_v == exp_v
        correct += ok
        if pred_v == "APPROVE" and exp_v != "APPROVE":
            false_approve += 1
        if pred_v == "REJECT" and exp_v != "REJECT":
            false_reject += 1

        exp_nm, pred_nm = "NAME_MISMATCH" in exp_codes, "NAME_MISMATCH" in pred_codes
        nm_tp += exp_nm and pred_nm
        nm_fp += pred_nm and not exp_nm
        nm_fn += exp_nm and not pred_nm
        rows.append((c["id"], exp_v, pred_v, "PASS" if ok else "FAIL"))

    nonapprove = sum(1 for c in cases if c["expected_verdict"] != "APPROVE") or 1
    return {
        "total": total,
        "accuracy": correct / total,
        "false_approve_count": false_approve,
        "false_approve_rate": false_approve / nonapprove,
        "false_reject_count": false_reject,
        "false_reject_rate": false_reject / total,
        "name_mismatch_precision": nm_tp / (nm_tp + nm_fp) if (nm_tp + nm_fp) else 1.0,
        "name_mismatch_recall": nm_tp / (nm_tp + nm_fn) if (nm_tp + nm_fn) else 1.0,
        "rows": rows,
    }


def main() -> None:
    m = evaluate()
    print("=" * 64)
    print("ClearKYC eval report — deterministic engine")
    print("=" * 64)
    for id_, ev, pv, st in m["rows"]:
        mark = " " if st == "PASS" else "X"
        print(f" [{mark}] {id_:22s} expected={ev:9s} predicted={pv}")
    print("-" * 64)
    print(f" cases:              {m['total']}")
    print(f" verdict accuracy:   {m['accuracy']:.1%}")
    print(f" false-approve rate: {m['false_approve_rate']:.1%}  (n={m['false_approve_count']})   <- regulatory risk")
    print(f" false-reject rate:  {m['false_reject_rate']:.1%}  (n={m['false_reject_count']})   <- merchant churn risk")
    print(f" name-mismatch P/R:  {m['name_mismatch_precision']:.0%} / {m['name_mismatch_recall']:.0%}")
    print("=" * 64)


if __name__ == "__main__":
    main()
