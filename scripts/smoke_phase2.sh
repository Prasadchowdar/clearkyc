#!/usr/bin/env bash
# Phase 2 end-to-end (mock extractor + mock embedder + deterministic reasoner).
# Demonstrates: (1) the RAG knowledge base is seeded, (2) decisions now carry
# rule-grounded CITATIONS, (3) the name-mismatch case is explained by the actual
# RBI rule behind it.
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"

new_case () { curl -fsS -X POST "$BASE/cases" -H 'content-type: application/json' \
  -d '{"merchant_id":"'"$1"'","type":"ONBOARD"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])'; }
add_doc () { curl -fsS -X POST "$BASE/cases/$1/documents" -H 'content-type: application/json' \
  -d '{"type":"'"$2"'","file_ref":"'"$3"'"}' >/dev/null; }

echo "=== Compliance knowledge base (RAG corpus) ==="
curl -fsS "$BASE/rules" | python3 -m json.tool

echo
echo "=== Mismatch case -> NEEDS_FIX, now GROUNDED in a cited rule ==="
B=$(new_case MISMATCH_P2)
add_doc "$B" PAN  /srv/fixtures/mismatch_pan.json
add_doc "$B" BANK /srv/fixtures/mismatch_bank.json
curl -fsS -X POST "$BASE/cases/$B/decide" \
  | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("verdict:", d["verdict"], "| confidence:", d["confidence"], "| engine:", d["engine_version"])
for r in d["reasons"]:
    c = r.get("citation", {})
    print(" reason:", r["detail"])
    print("   grounded in:", c.get("rule_id"), "->", c.get("source"))
    print("   rule text  :", c.get("snippet"))
'

echo
echo "=== Clean case (cosmetic difference) -> APPROVE ==="
A=$(new_case CLEAN_P2)
add_doc "$A" PAN  /srv/fixtures/clean_pan.json
add_doc "$A" BANK /srv/fixtures/clean_bank.json
curl -fsS -X POST "$BASE/cases/$A/decide" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("verdict:",d["verdict"],"| confidence:",d["confidence"])'
echo "OK"
