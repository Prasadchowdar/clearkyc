# ClearKYC — turning Razorpay's #1 merchant complaint into an AI agent

## The problem (researched, not assumed)

Razorpay is rated **1.4/5 on Trustpilot** and **1.7/5 on PissedConsumer**. The
complaints aren't about missing features — Razorpay already has mature products
for disputes, payment retries, reconciliation, and fraud. The wound is one
broken workflow:

**The KYC / settlement-hold black box.** Real, repeated merchant reports:
- Settlements frozen and **funds held for 120 days** with vague reasons.
- **KYC rejected by generic templated email**, no specific cause. Industry data:
  **~40% of KYC rejections are a name mismatch** across PAN/GST/bank (e.g.
  "Pvt. Ltd." vs "Private Limited").
- Support that doesn't act — one question every 48–72 hours, no human.

Razorpay's **own April 2026 compliance blog** confirms the mechanism: KYC name
mismatches trigger frozen funds and deactivation under PMLA, and 2025 RBI rules
made it stricter. This is a live, worsening problem — and it is exactly the kind
of broken internal workflow the AI hacker team exists to rebuild.

## What ClearKYC does

When a merchant is flagged, ClearKYC replaces the black box with a transparent
loop:

1. **Reads the documents** (OpenAI vision) — PAN, GST, bank, registration.
2. **Verifies identity** — normalizes Indian legal names so cosmetic differences
   are *not* rejected, then cross-checks names and validates PAN/GSTIN(+checksum)/IFSC.
3. **Grounds the decision** — RAG over real RBI/PMLA/format rules (pgvector).
4. **Reasons to a verdict** — APPROVE / NEEDS_FIX / REJECT, each reason **citing
   the specific rule** behind it.
5. **Drafts a human message** — specific and actionable, the opposite of the
   generic template.
6. **Guardrails + human-in-the-loop** — never auto-approves over a HIGH finding,
   never permanently rejects a fixable case; REJECT/low-confidence route to a
   human. Every step is written to an **append-only audit trail**.

## Why it's technically deep (not a vibe-coded demo)

- **Vision + RAG + agentic reasoning** behind one stable output contract.
- **Provider-agnostic**: mock (free/deterministic) and OpenAI (real) paths for
  extraction, embeddings, and reasoning — one env var switches them.
- **A measured eval harness** with a labeled golden set. Current numbers on the
  deterministic engine:

  | metric | value |
  |---|---|
  | verdict accuracy | **100%** |
  | false-approve rate (regulatory risk) | **0%** |
  | false-reject rate (merchant churn) | **0%** |
  | name-mismatch precision / recall | **100% / 100%** |

- **A real engineering story**: the LLM reasoner initially over-rejected a
  *fixable* name mismatch (REJECT, confidence 1.0). The eval caught it; the fix
  was a sharper prompt **plus** a deterministic guardrail. After: NEEDS_FIX,
  confidence 0.9. *"My agent was wrong, my guardrail caught it, my evals quantify
  it"* — that is the difference between building an agent and trusting one.

## Architecture

See the diagram in [README](./README.md).

## Run it

```bash
docker compose up --build -d
open http://localhost:8000/ui/     # reviewer console
bash scripts/demo.sh               # narrated CLI demo
python -m pytest -q                # 22 tests incl. the eval gate
python evals/run_evals.py          # the metrics report
```

## Stack

FastAPI · SQLAlchemy 2.0 · Postgres + pgvector · OpenAI (vision, embeddings,
reasoning) · rapidfuzz · Docker Compose · Python 3.13.
