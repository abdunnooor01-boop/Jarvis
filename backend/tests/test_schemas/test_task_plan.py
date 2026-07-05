"""Tests for task plan schemas."""

from __future__ import annotations

import uuid

from app.schemas.task_plan import (
    PlanGenerationRequest,
    PlanGenerationResponse,
    TaskPlanCreate,
    TaskPlanListResponse,
    TaskPlanResponse,
    TaskStepCreate,
    TaskStepResponse,
)


def test_task_plan_create_valid() -> None:
    """Test valid TaskPlanCreate schema."""
    data = TaskPlanCreate(goal="Search the web for documentation")
    assert data.goal == "Search the web for documentation"


def test_task_plan_create_empty_goal() -> None:
    """Test TaskPlanCreate with empty goal fails validation."""
    import pydantic

    try:
        TaskPlanCreate(goal="")
        assert False, "Should have raised ValidationError"
    except pydantic.ValidationError:
        pass


def test_task_step_create_valid() -> None:
    """Test valid TaskStepCreate schema."""
    step = TaskStepCreate(
        step_number=1,
        description="Search the web",
        tool_name="web_search",
        tool_params={"query": "Python"},
    )
    assert step.step_number == 1
    assert step.tool_name == "web_search"
    assert step.tool_params == {"query": "Python"}


def test_task_step_create_default_params() -> None:
    """Test TaskStepCreate default tool_params."""
    step = TaskStepCreate(
        step_number=1,
        description="Search",
        tool_name="web_search",
    )
    assert step.tool_params == {}


def test_task_step_create_invalid_step_number() -> None:
    """Test TaskStepCreate with step_number < 1 fails."""
    import pydantic

    try:
        TaskStepCreate(step_number=0, description="test", tool_name="web_search")
        assert False, "Should have raised ValidationError"
    except pydantic.ValidationError:
        pass


def test_task_step_response_from_attributes() -> None:
    """Test TaskStepResponse can be constructed."""
    step_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    response = TaskStepResponse(
        id=step_id,
        plan_id=plan_id,
        step_number=1,
        description="Test step",
        tool_name="web_search",
        tool_params={"query": "test"},
        status="pending",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    assert response.id == step_id
    assert response.status == "pending"
    assert response.tool_name == "web_search"


def test_task_plan_response_from_attributes() -> None:
    """Test TaskPlanResponse can be constructed."""
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    response = TaskPlanResponse(
        id=plan_id,
        user_id=user_id,
        goal="Test goal",
        status="running",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    assert response.id == plan_id
    assert response.status == "running"
    assert response.goal == "Test goal"


def test_task_plan_response_with_steps() -> None:
    """Test TaskPlanResponse with nested steps."""
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    step = TaskStepResponse(
        id=uuid.uuid4(),
        plan_id=plan_id,
        step_number=1,
        description="Step 1",
        tool_name="web_search",
        status="pending",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    response = TaskPlanResponse(
        id=plan_id,
        user_id=user_id,
        goal="Test",
        status="pending",
        steps=[step],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    assert len(response.steps) == 1
    assert response.steps[0].description == "Step 1"


def test_task_plan_list_response() -> None:
    """Test TaskPlanListResponse pagination."""
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan = TaskPlanResponse(
        id=plan_id,
        user_id=user_id,
        goal="Test",
        status="pending",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    response = TaskPlanListResponse(
        items=[plan],
        total=1,
        page=1,
        page_size=20,
        pages=1,
    )
    assert len(response.items) == 1
    assert response.total == 1


def test_plan_generation_request_valid() -> None:
    """Test valid PlanGenerationRequest."""
    request = PlanGenerationRequest(goal="Do something")
    assert request.goal == "Do something"


def test_plan_generation_request_empty() -> None:
    """Test PlanGenerationRequest with empty goal."""
    import pydantic

    try:
        PlanGenerationRequest(goal="")
        assert False
    except pydantic.ValidationError:
        pass


def test_plan_generation_response() -> None:
    """Test PlanGenerationResponse."""
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    plan = TaskPlanResponse(
        id=plan_id,
        user_id=user_id,
        goal="Test",
        status="pending",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    response = PlanGenerationResponse(plan=plan)
    assert response.plan.id == plan_id
    assert response.message == "Plan generated successfully"