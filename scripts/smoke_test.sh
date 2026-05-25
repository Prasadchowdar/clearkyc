#!/usr/bin/env bash
# End-to-end smoke test for the Phase 0 walking skeleton.
# Assumes the API is up on http://localhost:8000 (docker compose up).
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"

echo "1) health"
curl -fsS "$BASE/health"; echo

echo "2) create case"
CASE_ID=$(curl -fsS -X POST "$BASE/cases" \
  -H 'content-type: application/json' \
  -d '{"merchant_id":"MERCH_001","type":"ONBOARD"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["case_id"])')
echo "   case_id=$CASE_ID"

echo "3) decide with NO documents (expect NEEDS_FIX)"
curl -fsS -X POST "$BASE/cases/$CASE_ID/decide" | python3 -m json.tool

echo "4) add PAN + BANK documents"
curl -fsS -X POST "$BASE/cases/$CASE_ID/documents" \
  -H 'content-type: application/json' \
  -d '{"type":"PAN","file_ref":"s3://demo/pan.png"}' >/dev/null
curl -fsS -X POST "$BASE/cases/$CASE_ID/documents" \
  -H 'content-type: application/json' \
  -d '{"type":"BANK","file_ref":"s3://demo/bank.png"}' >/dev/null

echo "5) decide again (expect APPROVE, human_status PENDING due to low P0 confidence)"
curl -fsS -X POST "$BASE/cases/$CASE_ID/decide" | python3 -m json.tool

echo "6) fetch full case"
curl -fsS "$BASE/cases/$CASE_ID" | python3 -m json.tool

echo "OK"
