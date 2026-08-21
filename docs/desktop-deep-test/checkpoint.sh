#!/usr/bin/env bash
# checkpoint.sh <step> <status> [extra note]
# Writes a PASS/FAIL marker into results/ and pushes it immediately.
# Usage: checkpoint.sh safety-terminal PASS "12 passed"
set -uo pipefail
STEP="$1"; STATUS="$2"; NOTE="${3:-}"
TS=$(date -u +%Y%m%d-%H%M)
F="results/${TS}-${STEP}-${STATUS}.md"
{
  echo "# ${STEP} — ${STATUS}"
  echo
  echo "- status: ${STATUS}"
  echo "- time (UTC): $(date -u +%Y-%m-%d %H:%M:%S)"
  echo "- note: ${NOTE}"
  echo "- git: $(git rev-parse --short HEAD 2>/dev/null)"
  echo "- repo: $(pwd)"
} > "$F"
git add -A "$F" >/dev/null 2>&1
git commit -q -m "checkpoint: ${STEP} ${STATUS}" >/dev/null 2>&1
git push -q origin qa/deep-test-results >/dev/null 2>&1 && echo "PUSHED ${F}" || echo "PUSH_FAILED ${F}"
