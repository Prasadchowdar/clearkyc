#!/usr/bin/env bash
# Phase 1 end-to-end test (mock extractor). Demonstrates the two cases that
# matter most:
#   A) cosmetic name difference ("Pvt. Ltd." vs "Private Limited") -> APPROVE
#   B) genuinely different names -> NEEDS_FIX with a specific, explained reason
# Fixtures are mounted in the API container at /srv/fixtures.
set -euo pipefail
BASE="${BASE:-http://localhost:8000}"

new_case () { curl -fsS -X POST "$BASE/cases" -H 'content-type: application/json' \
  -d '{"merchant_id":"'"$1"'","type":"ONBOARD"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])'; }

add_doc () { curl -fsS -X POST "$BASE/cases/$1/documents" -H 'content-type: application/json' \
  -d '{"type":"'"$2"'","file_ref":"'"$3"'"}' >/dev/null; }

echo "=== CASE A: cosmetic difference (Pvt. Ltd. vs Private Limited) -> expect APPROVE ==="
A=$(new_case CLEAN_001)
add_doc "$A" PAN  /srv/fixtures/clean_pan.json
add_doc "$A" BANK /srv/fixtures/clean_bank.json
curl -fsS -X POST "$BASE/cases/$A/decide" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("verdict:",d["verdict"],"| confidence:",d["confidence"],"| human:",d["human_status"])'

echo
echo "=== CASE B: different names (ACME vs Globex) -> expect NEEDS_FIX ==="
B=$(new_case MISMATCH_001)
add_doc "$B" PAN  /srv/fixtures/mismatch_pan.json
add_doc "$B" BANK /srv/fixtures/mismatch_bank.json
curl -fsS -X POST "$BASE/cases/$B/decide" | python3 -m json.tool
echo "--- findings ---"
curl -fsS "$BASE/cases/$B/findings" | python3 -m json.tool
echo "OK"
