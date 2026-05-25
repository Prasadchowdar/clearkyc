"""Wire the eval harness into the test suite as a CI quality gate.

If a future change regresses the decision engine — e.g. starts false-approving
or false-rejecting — these assertions fail the build.
"""

from evals.run_evals import evaluate


def test_engine_meets_quality_bar():
    m = evaluate()
    # Hard gate: a KYC engine must never wrongly approve a bad case.
    assert m["false_approve_rate"] == 0.0, m
    # The deterministic engine must never permanently reject a fixable case.
    assert m["false_reject_rate"] == 0.0, m
    # Overall correctness and the headline name-mismatch recall.
    assert m["accuracy"] >= 0.95, m
    assert m["name_mismatch_recall"] >= 0.95, m
    assert m["name_mismatch_precision"] >= 0.95, m
