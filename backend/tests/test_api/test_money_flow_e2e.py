"""Phase 15 QA — SaaS money-flow end-to-end (MOCKED Stripe, no real charge).

This is one leg of the owner's desktop deep-test gate. It drives the full
money path a paying SaaS-testing / freelance customer would go through,
against the merged develop (HEAD = the PR #53 control-layer fix), but with a
MOCKED Stripe adapter so that NO real charge, NO payment link and NO revenue
catalog product are created:

    plan -> run -> completed (results written) -> report generated
    -> task-queue -> freelance order

Safety assertions at the end prove no revenue catalog product was created and
no real money moved (subscription uses the mock path; the freelance order is
created WITHOUT a Stripe payment link because no Stripe key is configured).

The actual browser/vision legs of the test engine are NOT exercised here (that
is environment-dependent); the run's "work is done" step is emulated by a
deterministic completion routine that writes real TestResult rows and marks the
run completed — exactly what the real engine does after executing criteria —
so the report generator has real data to render.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.freelance_task import FreelanceJob
from app.models.task_queue import TaskQueueItem
from app.models.testing import TestResult, TestRun

from tests.conftest import test_session_factory


@pytest_asyncio.fixture
async def authed(client: Any) -> tuple[Any, str]:
    """Register a fresh user and return (client, access_token)."""
    import uuid as _uuid

    email = f"money-{_uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "TestPassword123",
            "display_name": "Money Flow Tester",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return client, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _complete_run(run_id: str, criteria_count: int = 1) -> None:
    """Emulate the engine finishing a test run (writes results, marks done).

    Mirrors what TestingEngine.run_test_plan does to the DB after executing
    each criterion against a site, but without requiring a live browser / vision
    service in this headless QA environment.
    """
    now = datetime.now(UTC)
    async with test_session_factory() as db:
        run = (
            await db.execute(select(TestRun).where(TestRun.id == uuid.UUID(str(run_id))))
        ).scalar_one()
        run.status = "running"
        run.started_at = now
        await db.commit()

        run.status = "completed"
        run.completed_at = now
        run.total_tests = criteria_count
        run.passed = criteria_count
        run.failed = 0
        for i in range(criteria_count):
            db.add(
                TestResult(
                    id=uuid.uuid4(),
                    run_id=run.id,
                    step_number=i + 1,
                    criterion=f"criterion {i + 1}",
                    test_type="page_load",
                    passed=True,
                    detail="Verified OK",
                    duration_ms=10,
                )
            )
        await db.commit()


@pytest.mark.asyncio
async def test_saas_money_flow_e2e_mocked_stripe(
    authed: tuple[Any, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """plan -> run -> completed -> report -> task-queue -> freelance order (no $ moves)."""
    client, token = authed
    headers = _auth(token)
    # Guard: no Stripe key configured => the API's graceful mock path is used.
    from app.api import testing as testing_api
    from app.api import freelance as freelance_api
    from app.config import settings

    assert not settings.stripe_secret_key, (
        "Test must run with NO Stripe key so the mock adapter is exercised."
    )

    # Non-browser run completion.
    from app.services import test_report as test_report_module

    monkeypatch.setattr(
        testing_api._testing_engine, "run_test_plan", _complete_run
    )
    # Report generator reads the DB through its own factory; point it at the test DB.
    monkeypatch.setattr(test_report_module, "async_session_factory", test_session_factory)

    # 1) Subscription (MOCKED Stripe) — a SaaS-testing customer signs up.
    r = await client.post(
        "/api/v1/testing/subscription", json={"tier": "pro"}, headers=headers
    )
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["status"] == "active", sub
    assert (sub["stripe_subscription_id"] or "").startswith("mock_sub_"), (
        "Expected the MOCK Stripe path (no real subscription object)."
    )

    # 2) Plan — customer defines what to test.
    r = await client.post(
        "/api/v1/testing/plans",
        json={
            "name": "Checkout QA Plan",
            "url": "https://example-store.test",
            "test_criteria": "The checkout button should be visible; the page should load",
            "schedule": "manual",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    plan = r.json()
    plan_id = plan["id"]

    # 3) Run (trigger) — Jarvis performs the QA work.
    r = await client.post(f"/api/v1/testing/plans/{plan_id}/run", headers=headers)
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]

    # 4) Completed (results written) — poll for completion.
    completed = False
    for _ in range(50):
        await asyncio.sleep(0.1)
        r = await client.get(f"/api/v1/testing/runs/{run_id}", headers=headers)
        assert r.status_code == 200, r.text
        run = r.json()
        if run["status"] == "completed":
            completed = True
            break
    assert completed, "Test run did not reach 'completed' state"
    assert run["passed"] >= 1, run
    assert len(run["results"]) >= 1, run

    # 5) Report generated — the deliverable a paying customer receives.
    r = await client.post(
        f"/api/v1/testing/{run_id}/report", headers=headers
    )
    assert r.status_code == 200, r.text
    assert "Report generated at" in r.json()["message"], r.text

    # 6) Task-queue — submitted for server-side/offline execution.
    r = await client.post(
        "/api/v1/queue",
        json={
            "task_type": "test",
            "params": {"run_id": run_id},
            "metadata": {"source": "e2e"},
            "source_device": "desktop",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    queue_task_id = r.json()["id"]

    # 7) Freelance order — a separate paid-work channel (MOCKED Stripe, no link).
    r = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "buyer@example.com",
            "customer_name": "Buyer",
            "description": "Test my login page for broken states",
        },
    )
    assert r.status_code == 201, r.text
    order = r.json()
    job_id = order["job_id"]
    assert order["status"] == "pending", order
    assert order["amount_cents"] > 0, order

    # ------------------------------------------------------------------ #
    # SAFETY: NO revenue catalog product created, NO real money moved.
    # ------------------------------------------------------------------ #
    # The subscription used the mock adapter (no Stripe Price/Product/Checkout).
    assert not (sub["stripe_customer_id"]), sub
    # The freelance order must NOT carry a real Stripe payment link (no charge).
    assert order.get("stripe_payment_link") is None, order
    # No catalog product / price objects were created anywhere:
    # confirm the job was persisted without any Stripe identifiers.
    async with test_session_factory() as db:
        job = (
            await db.execute(
                select(FreelanceJob).where(FreelanceJob.id == uuid.UUID(job_id))
            )
        ).scalar_one()
        assert job.stripe_payment_link is None, "A Stripe payment link must not be created in mock mode"
        assert job.stripe_session_id is None
        # The queue task is persisted.
        qrow = (
            await db.execute(
                select(TaskQueueItem).where(TaskQueueItem.id == uuid.UUID(queue_task_id))
            )
        ).scalar_one()
        assert qrow is not None

    # No real key is configured -> the Stripe SDK was never pointed at live creds.
    assert not settings.stripe_secret_key
    assert not testing_api.settings.stripe_secret_key
    assert not freelance_api.settings.stripe_secret_key
