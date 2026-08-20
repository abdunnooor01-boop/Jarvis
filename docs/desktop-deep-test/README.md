# Phase 15 — Desktop Deep-Test Runbook (one-pass gate)

This is the **owner-gated** deep test that must pass before Jarvis takes ANY real
paid work (SaaS testing runs, freelance jobs, or any revenue transaction). It is
the **only** surface that flips the switch to revenue — no products may be
created in the revenue catalog until this gate AND the owner's guided laptop
smoke are both complete.

The whole point is **one uninterrupted pass inside a single stable window**
(~10 minutes run cold). The environment has a ~10–15 minute wipe cadence that
destroys member homes, `/home/team/shared`, and `/tmp` — so **GitHub is the only
durable surface**. This runbook lives in the repo so it survives wipes and can be
re-run identically from any fresh clone.

## What the gate verifies

| # | Step | What passes |
|---|------|-------------|
| a | Safety/control suite | `tests/test_tools/test_terminal_destructive.py` (destructive-command block matrix) + `tests/test_tools/test_computer_control.py` green |
| b | SaaS money-flow E2E | `test_freelance.py`, `test_freelance_freeform.py`, `test_task_queue.py`, `test_testing.py`, `test_testing_engine.py` — plan → run → completed → report → task-queue → freelance order, with **mocked Stripe + in-memory DB (no real charge)** |
| c | Electron package | `electron-vite build` + `electron-builder --dir --linux` from `frontend/` → `frontend/dist/linux-unpacked/` |
| d | Launch smoke | packaged app boots headless under `xvfb-run --no-sandbox` and stays alive |

The approval-gated control layer (hosted-mode blocking, approval fail-safes) is
covered separately by `test_tool_policy.py` + `test_ws_tool_approval_safety.py`
(now 6/6 after PR #53) — run those too for the full control-layer check, see
"Full suite" below.

## Single command (fresh clone, cold)

```bash
git clone --branch develop https://github.com/abdunnooor01-boop/Jarvis.git
cd Jarvis
bash docs/desktop-deep-test/deep-test.sh "$(pwd)"
```

That's it. The script handles clone-dir-agnostic paths, builds the backend venv,
installs frontend deps, and runs (a) → (d) in order. Finished steps are recorded
in `docs/desktop-deep-test/.state` (gitignored) and are **skipped on re-run**, so a
kill-and-restart resumes right where it stopped instead of redoing everything.

## Resume command (after a failed step, same window)

```bash
bash docs/desktop-deep-test/deep-test.sh "$(pwd)"
```

- If a step failed, the script prints the failing log tail (under `/tmp/gate_*.log`)
  and exits non-zero. Fix the root cause, then re-run — it picks up from the first
  not-yet-passing step.
- Multi-minute installs are cached by marker files for the life of the window; pass
  `SKIP_INSTALL=1` only if you've already built `.venv`/`node_modules` in this window.

## Exact resume commands (by hand, if you prefer not to use the script)

```bash
# 1) Fresh clone
git clone --branch develop https://github.com/abdunnooor01-boop/Jarvis.git && cd Jarvis

# 2) Backend venv + deps (ONNX-only — skip silero-vad/torch, saves ~4.6GB & minutes)
cd backend
python3 -m venv .venv
grep -vE '^(#.*)?$' requirements.txt | grep -vE '^(silero-vad|torch)([<>=!]|$)' > /tmp/jarvis_rq.txt
./.venv/bin/pip install --no-cache-dir -q -r /tmp/jarvis_rq.txt requirements-dev.txt
export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite://}"

# 3) (a) safety/control suite
./.venv/bin/python -m pytest tests/test_tools/test_terminal_destructive.py tests/test_tools/test_computer_control.py -q

# 4) (b) money-flow E2E (mocked Stripe, in-memory DB — no real charge)
./.venv/bin/python -m pytest tests/test_api/test_freelance.py tests/test_api/test_freelance_freeform.py \
  tests/test_api/test_task_queue.py tests/test_api/test_testing.py tests/test_services/test_testing_engine.py -q

# 5) (c) electron package (from frontend/)
cd ../frontend
npm install --no-audit --no-fund
npm run build                 # electron-vite build -> frontend/out/
npx electron-builder --dir --linux   # -> frontend/dist/linux-unpacked/

# 6) (d) headless launch smoke (packaged binary is in dist/linux-unpacked/)
xvfb-run -a ./dist/linux-unpacked/jarvis-frontend --no-sandbox --disable-gpu &
APP_PID=$!; sleep 8; kill $APP_PID   # PASS = it survived 8s without crashing
```

## Full control-layer suite (recommended alongside the gate)

```bash
cd backend
./.venv/bin/python -m pytest tests/test_services/test_tool_policy.py tests/test_api/test_ws_tool_approval_safety.py -q
```

## Outputs / logs

- Gate logs: `/tmp/gate_safety.log`, `/tmp/gate_money.log`, `/tmp/gate_electron.log`, `/tmp/gate_xvfb.log`
- Packaged app: `frontend/dist/linux-unpacked/`
- State / resume marker: `docs/desktop-deep-test/.state` (gitignored, rebuilt per fresh clone)

## After the gate passes

1. Run the owner's **guided laptop smoke** on their own machine (approval UI, chat +
   TTS + tool frames, IPC executor, real desktop context).
2. Only then create the revenue catalog (SaaS testing plans $50–200/mo, freelance
   tiers) and take the first paying customer.
3. **Do NOT** open the revenue catalog / create any Stripe product before this gate
   + laptop smoke are complete.
