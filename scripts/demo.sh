#!/usr/bin/env bash
# Narrated end-to-end demo of ClearKYC. Run after `docker compose up -d`.
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"
pause () { sleep "${DEMO_PAUSE:-1}"; }
line () { printf '\n\033[1;36m%s\033[0m\n' "$*"; }

line "ClearKYC — Merchant Risk & Compliance Copilot"
echo  "The KYC/settlement-hold black box is Razorpay's #1 merchant complaint."
echo  "ClearKYC turns it into a transparent, grounded, audited decision."
pause

line "1) The compliance knowledge base (RAG corpus, embedded in pgvector)"
curl -fsS "$BASE/rules" | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("  %d rules seeded:" % d["count"])
for r in d["rules"]:
    print("   -", r["rule_id"])'
pause

line "2) A CLEAN merchant (name differs only cosmetically: Pvt. Ltd. vs Private Limited)"
curl -fsS -X POST "$BASE/demo/clean" | python3 -c '
import sys, json
c = json.load(sys.stdin); d = c["decisions"][-1]
print("  verdict: %s  confidence: %.0f%%  human: %s" % (d["verdict"], d["confidence"]*100, d["human_status"]))
print("  -> the cosmetic difference Razorpay wrongly rejects 40% of the time is APPROVED.")'
pause

line "3) A REAL problem (name mismatch) — explained and GROUNDED in the actual rule"
curl -fsS -X POST "$BASE/demo/mismatch" | python3 -c '
import sys, json
c = json.load(sys.stdin); d = c["decisions"][-1]
print("  verdict: %s  confidence: %.0f%%  human: %s" % (d["verdict"], d["confidence"]*100, d["human_status"]))
for r in d["reasons"]:
    print("  reason:", r["detail"])
    cit = r.get("citation", {})
    print("    grounded in:", cit.get("rule_id"), "->", cit.get("source"))
print("  drafted message:", d["drafted_message"][:120], "...")'
pause

line "Open the reviewer console for the full visual flow + human-in-the-loop:"
echo  "  $BASE/ui/"
echo
echo "Done."
