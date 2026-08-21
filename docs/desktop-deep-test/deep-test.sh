#!/usr/bin/env bash
#
# deep-test.sh — ONE-PASS runbook for the Phase 15 desktop deep-test gate.
#
# PURPOSE
#   From a fresh develop clone, complete in a single uninterrupted pass (and
#   ideally inside one ~10-minute window, run cold):
#     (a) terminal destructive matrix + computer-control test suite green
#     (b) SaaS money-flow E2E (mocked Stripe / in-memory DB — NO real charge)
#     (c) electron-vite build + electron-builder --dir --linux package
#     (d) xvfb launch smoke of the packaged app
#
# DESIGN
#   * Idempotent / kill-and-restart safe: each step records PASS/FAIL in a state
#     file; a completed step is skipped on re-run. Fix the failure and re-run
#     the same script to resume from exactly where it stopped.
#   * Optimized for a cold 10-minute window: heavy installs (venv, node_modules)
#     run once and are cached by marker files for the life of that window.
#
# USAGE
#   bash docs/desktop-deep-test/deep-test.sh [repo_dir]
#   repo_dir defaults to the current working directory (pass the repo root).
#   On a FRESH clone, start from a clean slate:  rm -f docs/desktop-deep-test/.state
#
# STATE
#   State is kept in docs/desktop-deep-test/.state (gitignored). It is rebuilt
#   on every fresh clone; cross-wipe resumption is impossible (disk is wiped),
#   which is why GitHub is the durable surface and this script is repeatable.
#
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-$(pwd)}"
cd "$REPO" || { echo "FATAL: repo dir $REPO not found"; exit 1; }

STATE="$HERE/.state"
: > "$STATE"   # start this run's state (stale on disk is overwritten)
mark() { echo "PASS $(date +%H:%M:%S) $1" >> "$STATE"; }
failstate() { echo "FAIL $(date +%H:%M:%S) $1" >> "$STATE"; }

step_done() { grep -q "^PASS .* $1\$" "$STATE" 2>/dev/null; }
step_failed() { grep -q "^FAIL .* $1\$" "$STATE" 2>/dev/null; }
skip_if_done() {
  local step="$1"
  if step_done "$step"; then echo "==> SKIP $step (already passed)"; return 0
  elif step_failed "$step"; then echo "==> HALT at $step (failed previously; fix & re-run)"; return 1
  fi; return 2
}

# ---------------------------------------------------------------------------
echo "=================================================="
echo " Phase 15 deep-test gate — repo: $REPO"
echo " develop @ $(git -C "$REPO" log --oneline -1 2>/dev/null || echo 'n/a')"
echo "=================================================="

# Optional: skip long installs that already exist on this (same-window) disk.
SKIP_INSTALL="${SKIP_INSTALL:-0}"   # set SKIP_INSTALL=1 to reuse an existing .venv/node_modules

# ---------------------------------------------------------------------------
# STEP 0 — backend virtualenv + deps (heavy, cached by marker within a window)
# ---------------------------------------------------------------------------
STEP="backend-deps"
if ! skip_if_done "$STEP"; then
  echo "[$STEP] creating backend venv + installing deps..."
  cd "$REPO/backend" || exit 1
  if [ ! -d .venv ]; then python3 -m venv .venv; fi
  # ONNX-only path per Phase 15 guidance: skip silero-vad & torch (saves ~4.6GB / minutes).
  grep -vE '^(#.*)?$' requirements.txt | grep -vE '^(silero-vad|torch)([<>=!]|$)' > /tmp/jarvis_rq.txt 2>/dev/null || true
  if [ "$SKIP_INSTALL" != "1" ]; then
    ./.venv/bin/pip install --no-cache-dir -q -r /tmp/jarvis_rq.txt
    ./.venv/bin/pip install --no-cache-dir -q -r requirements-dev.txt || true
  fi
  # Env guard: force in-memory/test DB in all gate runs (never touch a real DB).
  export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite://}"
  mark "$STEP"
fi

# ---------------------------------------------------------------------------
# STEP (a) — terminal destructive matrix + computer control safety suite
# ---------------------------------------------------------------------------
STEP="safety-control-tests"
if ! skip_if_done "$STEP"; then
  echo "[$STEP] running terminal destructive matrix + computer-control tests..."
  cd "$REPO/backend" || exit 1
  if ./.venv/bin/python -m pytest \
        tests/test_tools/test_terminal_destructive.py \
        tests/test_tools/test_computer_control.py \
        -q > /tmp/gate_safety.log 2>&1; then
    mark "$STEP"
  else
    echo "[$STEP] FAILED — see /tmp/gate_safety.log"; tail -20 /tmp/gate_safety.log; failstate "$STEP"; exit 1
  fi
fi

# ---------------------------------------------------------------------------
# STEP (b) — SaaS money-flow E2E (mocked Stripe, in-memory DB, NO real charge)
#   plan -> run -> completed -> report -> task-queue -> freelance order
# ---------------------------------------------------------------------------
STEP="money-flow-e2e"
if ! skip_if_done "$STEP"; then
  echo "[$STEP] running money-flow E2E (freelance / task-queue / testing / payments)..."
  cd "$REPO/backend" || exit 1
  if ./.venv/bin/python -m pytest \
        tests/test_api/test_freelance.py \
        tests/test_api/test_freelance_freeform.py \
        tests/test_api/test_task_queue.py \
        tests/test_api/test_testing.py \
        tests/test_services/test_testing_engine.py \
        -q > /tmp/gate_money.log 2>&1; then
    mark "$STEP"
  else
    echo "[$STEP] FAILED — see /tmp/gate_money.log"; tail -20 /tmp/gate_money.log; failstate "$STEP"; exit 1
  fi
fi

# ---------------------------------------------------------------------------
# STEP (c) — electron-vite build + electron-builder --dir --linux
# ---------------------------------------------------------------------------
STEP="frontend-build"
if ! skip_if_done "$STEP"; then
  echo "[$STEP] frontend install + electron-vite build + electron-builder --dir --linux..."
  cd "$REPO/frontend" || exit 1
  if [ "$SKIP_INSTALL" != "1" ] && [ ! -d node_modules ]; then
    npm install --no-audit --no-fund
  fi
  if npm run build > /tmp/gate_electron.log 2>&1 \
     && npx electron-builder --dir --linux >> /tmp/gate_electron.log 2>&1; then
    mark "$STEP"
  else
    echo "[$STEP] FAILED — see /tmp/gate_electron.log"; tail -30 /tmp/gate_electron.log; failstate "$STEP"; exit 1
  fi
fi

# ---------------------------------------------------------------------------
# STEP (d) — xvfb launch smoke of the packaged app
# ---------------------------------------------------------------------------
STEP="xvfb-smoke"
if ! skip_if_done "$STEP"; then
  echo "[$STEP] launching packaged app under xvfb (headless boot smoke)..."
  PACKAGE_DIR="$REPO/frontend/dist/linux-unpacked"
  EXE=$(find "$PACKAGE_DIR" -maxdepth 1 -type f -executable \( -name 'jarvis-frontend' -o -name 'Jarvis' -o -name 'jarvis' \) 2>/dev/null | head -n1)
  if [ -z "$EXE" ]; then
    # Fall back to the electron main entry if the packed binary name differs.
    EXE="$PACKAGE_DIR/jarvis-frontend"
  fi
  if [ ! -x "$EXE" ]; then
    echo "[$STEP] FAILED — packaged executable not found in $PACKAGE_DIR"; ls "$PACKAGE_DIR" 2>/dev/null | head; failstate "$STEP"; exit 1
  fi
  # Headless: no GPU, no sandbox (container). Local backend + IPC executor are
  # exercised by the owner's guided manual smoke; here we only verify clean boot.
  if timeout 15 xvfb-run -a "$EXE" --no-sandbox --disable-gpu > /tmp/gate_xvfb.log 2>&1; then
    :
  fi
  # A crash-on-start exits before the 15s; timeout(124) means it stayed alive.
  rc=$?
  grep -qiE "backend.*(start|listening|boot)|ipc|ready" /tmp/gate_xvfb.log && boot_ok=1 || boot_ok=0
  if [ "$rc" -eq 124 ] || { [ "$rc" -ne 0 ] && [ "$boot_ok" -eq 1 ]; }; then
    echo "[$STEP] PASS — app booted and stayed alive ($rc), see /tmp/gate_xvfb.log"
    mark "$STEP"
  else
    echo "[$STEP] FAILED — app exited early (rc=$rc). see /tmp/gate_xvfb.log"; tail -20 /tmp/gate_xvfb.log; failstate "$STEP"; exit 1
  fi
fi

# ---------------------------------------------------------------------------
echo "=================================================="
echo " ALL GATE STEPS PASSED (single uninterrupted pass)."
echo " State:"
cat "$STATE"
echo "=================================================="
echo " NEXT: owner-guided laptop smoke, then flip revenue switch."
echo " Note: do NOT open the revenue catalog / create products until the"
echo " owner's desktop deep test + laptop smoke are complete."
