"""Tests for the Testing Service API endpoints.

Note: The API endpoints for testing (api/testing.py) have not been built yet.
This file tests the schemas and provides a template for API endpoint tests
once the routes are implemented.

Expected endpoints (per the Phase 12 spec):
- POST /api/v1/testing/runs — create a test run
- GET /api/v1/testing/runs — list runs
- GET /api/v1/testing/runs/{run_id} — get run detail
- POST /api/v1/testing/runs/{run_id}/trigger — trigger execution
- POST /api/v1/testing/webhook — CI/CD webhook
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.testing import (
    TestCriterionCreate,
    TestRunCreateRequest,
    TestRunResponse,
    TestResultResponse,
    TestRunListResponse,
    TestRunStatusResponse,
    TestRunActionResponse,
    WebhookTriggerResponse,
    WebhookPayload,
)


# ---------------------------------------------------------------------------
# Schema validation tests (no API endpoint needed)
# ---------------------------------------------------------------------------


class TestTestCriterionCreateSchema:
    """Tests for TestCriterionCreate schema validation."""

    def test_valid_criterion(self) -> None:
        """Test creating a valid criterion."""
        data = TestCriterionCreate(
            criterion="The login button should be visible",
            test_type="element_visibility",
        )
        assert data.criterion == "The login button should be visible"
        assert data.test_type == "element_visibility"

    def test_criterion_min_length(self) -> None:
        """Test criterion with empty string (should fail)."""
        with pytest.raises(ValidationError):
            TestCriterionCreate(criterion="", test_type="page_load")

    def test_criterion_max_length(self) -> None:
        """Test criterion exceeding max length (should fail)."""
        with pytest.raises(ValidationError):
            TestCriterionCreate(criterion="x" * 1001, test_type="page_load")

    @pytest.mark.parametrize("test_type", [
        "page_load", "element_visibility", "text_content",
        "link_click", "form_submission", "screenshot",
    ])
    def test_valid_test_types(self, test_type: str) -> None:
        """Test all valid test types."""
        data = TestCriterionCreate(
            criterion="Test the page",
            test_type=test_type,
        )
        assert data.test_type == test_type

    def test_invalid_test_type(self) -> None:
        """Test invalid test type (should fail)."""
        with pytest.raises(ValidationError):
            TestCriterionCreate(
                criterion="Test",
                test_type="invalid_type",
            )

    def test_default_test_type(self) -> None:
        """Test default test type is element_visibility."""
        data = TestCriterionCreate(criterion="Test the page")
        assert data.test_type == "element_visibility"


class TestTestRunCreateRequestSchema:
    """Tests for TestRunCreateRequest schema validation."""

    def test_valid_run(self) -> None:
        """Test creating a valid test run request."""
        data = TestRunCreateRequest(
            url="https://example.com",
            name="Smoke Test",
            criteria=[
                TestCriterionCreate(criterion="Page should load", test_type="page_load"),
                TestCriterionCreate(criterion="Button should be visible", test_type="element_visibility"),
            ],
        )
        assert data.url == "https://example.com"
        assert data.name == "Smoke Test"
        assert len(data.criteria) == 2

    def test_valid_run_no_name(self) -> None:
        """Test creating a run without a name."""
        data = TestRunCreateRequest(
            url="https://example.com",
            criteria=[TestCriterionCreate(criterion="Test", test_type="screenshot")],
        )
        assert data.name is None

    def test_empty_url(self) -> None:
        """Test empty URL (should fail)."""
        with pytest.raises(ValidationError):
            TestRunCreateRequest(
                url="",
                criteria=[TestCriterionCreate(criterion="Test", test_type="screenshot")],
            )

    def test_invalid_url_too_long(self) -> None:
        """Test URL exceeding max length (should fail)."""
        with pytest.raises(ValidationError):
            TestRunCreateRequest(
                url="https://" + "x" * 2040,
                criteria=[TestCriterionCreate(criterion="Test", test_type="screenshot")],
            )

    def test_empty_criteria(self) -> None:
        """Test empty criteria list (should fail, min_length=1)."""
        with pytest.raises(ValidationError):
            TestRunCreateRequest(
                url="https://example.com",
                criteria=[],
            )

    def test_too_many_criteria(self) -> None:
        """Test too many criteria (should fail, max_length=50)."""
        with pytest.raises(ValidationError):
            TestRunCreateRequest(
                url="https://example.com",
                criteria=[TestCriterionCreate(criterion="Test") for _ in range(51)],
            )


class TestTestRunResponseSchema:
    """Tests for TestRunResponse schema."""

    def test_minimal_response(self) -> None:
        """Test creating a response with minimal fields."""
        data = TestRunResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            url="https://example.com",
            status="pending",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert data.status == "pending"
        assert data.total_tests == 0
        assert data.results == []

    def test_full_response(self) -> None:
        """Test creating a response with all fields."""
        run_id = uuid.uuid4()
        result_id = uuid.uuid4()
        data = TestRunResponse(
            id=run_id,
            user_id=uuid.uuid4(),
            url="https://example.com",
            name="Full Test",
            status="completed",
            total_tests=3,
            passed=2,
            failed=1,
            report_path="/reports/test.html",
            results=[
                TestResultResponse(
                    id=result_id,
                    run_id=run_id,
                    step_number=1,
                    criterion="Page should load",
                    test_type="page_load",
                    passed=True,
                    detail="Loaded OK",
                    duration_ms=1500,
                    created_at="2026-01-01T00:00:00Z",
                ),
            ],
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T00:00:05Z",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:05Z",
        )
        assert data.status == "completed"
        assert data.passed == 2
        assert data.failed == 1
        assert len(data.results) == 1
        assert data.results[0].passed is True
        assert data.results[0].duration_ms == 1500


class TestTestRunListResponseSchema:
    """Tests for TestRunListResponse schema."""

    def test_empty_list(self) -> None:
        """Test empty list response."""
        data = TestRunListResponse(items=[], total=0)
        assert data.items == []
        assert data.total == 0
        assert data.page == 1
        assert data.page_size == 20
        assert data.pages == 1

    def test_paginated_list(self) -> None:
        """Test paginated list response."""
        items = [
            TestRunResponse(
                id=uuid.uuid4(),
                user_id=uuid.uuid4(),
                url=f"https://example.com/{i}",
                status="completed",
                created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z",
            )
            for i in range(5)
        ]
        total = 50
        page = 2
        page_size = 5
        pages = 10
        data = TestRunListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
        assert len(data.items) == 5
        assert data.total == 50
        assert data.page == 2
        assert data.pages == 10


class TestTestRunStatusResponseSchema:
    """Tests for TestRunStatusResponse schema."""

    def test_status_response(self) -> None:
        """Test status response with progress."""
        data = TestRunStatusResponse(
            id=uuid.uuid4(),
            url="https://example.com",
            status="running",
            total_tests=10,
            passed=4,
            failed=1,
            progress=0.5,
            started_at="2026-01-01T00:00:00Z",
        )
        assert data.status == "running"
        assert data.progress == 0.5
        assert data.passed == 4
        assert data.failed == 1


class TestWebhookPayloadSchema:
    """Tests for WebhookPayload schema."""

    def test_minimal_payload(self) -> None:
        """Test minimal webhook payload."""
        data = WebhookPayload()
        assert data.url is None
        assert data.ref is None
        assert data.event is None
        assert data.repository is None
        assert data.commit_sha is None
        assert data.extra == {}

    def test_full_payload(self) -> None:
        """Test full webhook payload."""
        data = WebhookPayload(
            url="https://example.com",
            ref="refs/heads/main",
            event="push",
            repository="myorg/myapp",
            commit_sha="abc123",
            extra={"branch": "main"},
        )
        assert data.url == "https://example.com"
        assert data.ref == "refs/heads/main"
        assert data.event == "push"
        assert data.repository == "myorg/myapp"
        assert data.commit_sha == "abc123"


class TestTestRunActionResponseSchema:
    """Tests for TestRunActionResponse schema."""

    def test_action_response(self) -> None:
        """Test action response."""
        data = TestRunActionResponse(
            run_id=uuid.uuid4(),
            status="running",
            message="Test run started",
        )
        assert data.status == "running"
        assert "started" in data.message


class TestWebhookTriggerResponseSchema:
    """Tests for WebhookTriggerResponse schema."""

    def test_webhook_response(self) -> None:
        """Test webhook trigger response."""
        data = WebhookTriggerResponse(
            run_id=uuid.uuid4(),
            status="pending",
            message="Webhook received, test run created",
            report_url="https://example.com/reports/run-123.html",
        )
        assert data.status == "pending"
        assert data.report_url is not None