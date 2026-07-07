"""Tests for freelance task catalog and payment API."""

from __future__ import annotations

import uuid

import pytest


async def _register_and_get_token(client: pytest.fixture) -> str:
    """Helper to register a test user and return a token."""
    import uuid as _uuid

    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"freelance-{_uuid.uuid4().hex[:8]}@example.com",
            "password": "FreeTest123",
            "display_name": "Freelance Tester",
        },
    )
    data = reg_resp.json()
    return data.get("access_token", "")


@pytest.mark.asyncio
async def test_list_templates_success(client: pytest.fixture) -> None:
    """Test listing task templates without auth."""
    resp = await client.get("/api/v1/freelance/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] > 0
    # Check first template has expected fields
    first = data["items"][0]
    assert "id" in first
    assert "name" in first
    assert "price_cents" in first
    assert "price_dollars" in first
    assert "category" in first


@pytest.mark.asyncio
async def test_list_templates_has_all_seeds(client: pytest.fixture) -> None:
    """Test that all 8 pre-seeded templates are present."""
    resp = await client.get("/api/v1/freelance/templates")
    data = resp.json()
    assert data["total"] == 8
    names = {t["name"] for t in data["items"]}
    assert "App Testing" in names
    assert "Copywriting" in names
    assert "Data Entry" in names
    assert "Web Research" in names
    assert "Content Writing" in names
    assert "Form Filling" in names
    assert "File Processing" in names
    assert "Email Drafting" in names


@pytest.mark.asyncio
async def test_list_templates_prices(client: pytest.fixture) -> None:
    """Test that template prices are correctly formatted."""
    resp = await client.get("/api/v1/freelance/templates")
    data = resp.json()
    for t in data["items"]:
        assert t["price_cents"] > 0
        assert t["price_dollars"] == round(t["price_cents"] / 100.0, 2)
        assert t["estimated_minutes"] > 0


@pytest.mark.asyncio
async def test_create_order_success(client: pytest.fixture) -> None:
    """Test creating a job order successfully."""
    # Get a template first
    resp = await client.get("/api/v1/freelance/templates")
    templates = resp.json()["items"]
    template_id = templates[0]["id"]

    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": template_id,
            "customer_email": "customer@example.com",
            "customer_name": "Test Customer",
            "description": "Please test my app thoroughly",
        },
    )
    assert order_resp.status_code == 201
    data = order_resp.json()
    assert "job_id" in data
    assert data["template_name"] == templates[0]["name"]
    assert data["amount_cents"] == templates[0]["price_cents"]
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_order_invalid_template(client: pytest.fixture) -> None:
    """Test creating an order with invalid template ID."""
    resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": str(uuid.uuid4()),
            "customer_email": "customer@example.com",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_order_invalid_email(client: pytest.fixture) -> None:
    """Test creating an order with invalid email."""
    resp = await client.get("/api/v1/freelance/templates")
    template_id = resp.json()["items"][0]["id"]

    resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": template_id,
            "customer_email": "not-an-email",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_jobs_requires_auth(client: pytest.fixture) -> None:
    """Test listing jobs returns 401 without auth."""
    resp = await client.get("/api/v1/freelance/jobs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_job_requires_auth(client: pytest.fixture) -> None:
    """Test getting job details returns 401 without auth."""
    resp = await client.get(f"/api/v1/freelance/jobs/{uuid.uuid4()}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_jobs_success(client: pytest.fixture) -> None:
    """Test listing jobs with auth."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        "/api/v1/freelance/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data


@pytest.mark.asyncio
async def test_get_job_not_found(client: pytest.fixture) -> None:
    """Test getting a non-existent job."""
    token = await _register_and_get_token(client)
    resp = await client.get(
        f"/api/v1/freelance/jobs/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_order_then_list_jobs(client: pytest.fixture) -> None:
    """Test creating an order and then seeing it in the jobs list."""
    token = await _register_and_get_token(client)

    # Get a template
    resp = await client.get("/api/v1/freelance/templates")
    template = resp.json()["items"][0]

    # Create order
    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": template["id"],
            "customer_email": "customer@example.com",
            "customer_name": "Test Customer",
        },
    )
    assert order_resp.status_code == 201
    job_id = order_resp.json()["job_id"]

    # List jobs should include it
    jobs_resp = await client.get(
        "/api/v1/freelance/jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert jobs_resp.status_code == 200
    job_ids = [j["id"] for j in jobs_resp.json()["items"]]
    assert job_id in job_ids


@pytest.mark.asyncio
async def test_get_job_detail(client: pytest.fixture) -> None:
    """Test getting a specific job's details."""
    token = await _register_and_get_token(client)

    resp = await client.get("/api/v1/freelance/templates")
    template = resp.json()["items"][0]

    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": template["id"],
            "customer_email": "customer@example.com",
        },
    )
    job_id = order_resp.json()["job_id"]

    detail_resp = await client.get(
        f"/api/v1/freelance/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == job_id
    assert detail["template_name"] == template["name"]
    assert detail["amount_cents"] == template["price_cents"]


@pytest.mark.asyncio
async def test_webhook_invalid_json(client: pytest.fixture) -> None:
    """Test webhook with non-JSON body."""
    resp = await client.post(
        "/api/v1/freelance/webhook",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_checkout_completed(client: pytest.fixture) -> None:
    """Test webhook marks job as paid on checkout.session.completed."""
    token = await _register_and_get_token(client)

    resp = await client.get("/api/v1/freelance/templates")
    template = resp.json()["items"][0]

    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": template["id"],
            "customer_email": "customer@example.com",
        },
    )
    job_id = order_resp.json()["job_id"]

    # Simulate Stripe webhook
    webhook_resp = await client.post(
        "/api/v1/freelance/webhook",
        json={
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"job_id": job_id},
                }
            },
        },
    )
    assert webhook_resp.status_code == 200
    assert webhook_resp.json()["status"] == "ok"

    # Verify job was marked as paid
    detail_resp = await client.get(
        f"/api/v1/freelance/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "paid"


@pytest.mark.asyncio
async def test_webhook_unknown_event(client: pytest.fixture) -> None:
    """Test webhook with unknown event type."""
    resp = await client.post(
        "/api/v1/freelance/webhook",
        json={
            "type": "unknown.event",
            "data": {"object": {}},
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"