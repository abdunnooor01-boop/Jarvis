"""Tests for freelance open-ended order intake and price estimation."""

from __future__ import annotations

import uuid

import pytest


@pytest.mark.asyncio
async def test_freeform_order_success(client):
    """Test creating a free-form order with just a description."""
    resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "customer@example.com",
            "description": "Test my login page for bugs and issues",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "job_id" in data
    assert data["template_name"] is None  # Free-form has no template
    assert data["amount_cents"] in (500, 1000, 2500)  # Falls back to medium ($10)
    assert data["status"] == "pending"
    assert "stripe_payment_link" in data


@pytest.mark.asyncio
async def test_freeform_order_no_description_fails(client):
    """Test creating an order without template_id or description fails."""
    resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "customer@example.com",
        },
    )
    assert resp.status_code == 400
    assert "Either template_id or description" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_freeform_order_then_list_jobs(client):
    """Test creating a free-form order and seeing it in the jobs list."""
    # Register a user
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"freeform-{uuid.uuid4().hex[:8]}@example.com",
            "password": "FreeTest123",
            "display_name": "Freeform Tester",
        },
    )
    token = reg_resp.json().get("access_token", "")

    # Create free-form order
    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "customer@example.com",
            "description": "Write a blog post about AI assistants",
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
async def test_freeform_get_job_detail(client):
    """Test getting a free-form job's details."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"freeform-{uuid.uuid4().hex[:8]}@example.com",
            "password": "FreeTest123",
            "display_name": "Detail Tester",
        },
    )
    token = reg_resp.json().get("access_token", "")

    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "customer@example.com",
            "description": "Scrape product prices from an e-commerce site",
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
    assert detail["template_id"] is None
    assert detail["template_name"] == ""
    assert "Scrape product prices" in (detail.get("description") or "")


@pytest.mark.asyncio
async def test_freeform_price_estimation_default(client):
    """Test that free-form gets the default medium price ($10) when no LLM key."""
    resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "customer@example.com",
            "description": "Draft a short thank you email",
        },
    )
    assert resp.status_code == 201
    # Without LLM key, defaults to medium ($10 = 1000 cents)
    data = resp.json()
    assert data["amount_cents"] == 1000


@pytest.mark.asyncio
async def test_template_id_takes_precedence(client):
    """Test that template_id takes precedence when both it and description are provided."""
    resp = await client.get("/api/v1/freelance/templates")
    template = resp.json()["items"][0]

    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "template_id": template["id"],
            "customer_email": "customer@example.com",
            "description": "Free-form description that should be ignored",
        },
    )
    assert order_resp.status_code == 201
    data = order_resp.json()
    assert data["template_name"] == template["name"]
    assert data["amount_cents"] == template["price_cents"]


@pytest.mark.asyncio
async def test_webhook_on_freeform_job(client):
    """Test Stripe webhook works with free-form jobs."""
    reg_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"freeform-{uuid.uuid4().hex[:8]}@example.com",
            "password": "FreeTest123",
            "display_name": "Webhook Tester",
        },
    )
    token = reg_resp.json().get("access_token", "")

    order_resp = await client.post(
        "/api/v1/freelance/order",
        json={
            "customer_email": "customer@example.com",
            "description": "Test my mobile app for UI bugs",
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
                    "id": "cs_test_freeform_456",
                    "metadata": {"job_id": job_id},
                }
            },
        },
    )
    assert webhook_resp.status_code == 200

    # Verify job was marked as paid
    detail_resp = await client.get(
        f"/api/v1/freelance/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "paid"
