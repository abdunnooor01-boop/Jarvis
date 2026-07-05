"""Tests for task planning service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.models.task_plan import TaskPlan
from app.models.task_step import TaskStep
from app.services.task_planner import TaskPlanner


@pytest_asyncio.fixture
async def task_planner() -> TaskPlanner:
    """Create a TaskPlanner instance for testing."""
    return TaskPlanner()


@pytest.mark.asyncio
async def test_get_available_tools(task_planner: TaskPlanner) -> None:
    """Test that available tools are returned."""
    tools = task_planner._get_available_tools()
    assert isinstance(tools, list)
    assert len(tools) > 0
    # Should include common tools
    tool_names = {t.get("function", {}).get("name") for t in tools}
    assert "web_search" in tool_names or "file_ops" in tool_names or "screen_vision" in tool_names


@pytest.mark.asyncio
async def test_is_tool_available(task_planner: TaskPlanner) -> None:
    """Test tool availability check."""
    tools = task_planner._get_available_tools()
    assert len(tools) > 0

    first_tool_name = tools[0].get("function", {}).get("name", "")
    assert task_planner._is_tool_available(first_tool_name, tools)

    assert not task_planner._is_tool_available("nonexistent_tool_xyz", tools)


@pytest.mark.asyncio
async def test_fallback_plan_no_api_key(task_planner: TaskPlanner) -> None:
    """Test fallback plan when no API key is configured."""
    tools = task_planner._get_available_tools()
    steps = task_planner._fallback_plan("Search the web for Python", tools)
    assert isinstance(steps, list)
    assert len(steps) >= 1
    assert steps[0].get("description")
    assert steps[0].get("tool_name")


@pytest.mark.asyncio
async def test_fallback_plan_keyword_match(task_planner: TaskPlanner) -> None:
    """Test fallback plan finds matching tool via keywords."""
    # Create simulated tools
    simulated_tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "screen_vision",
                "description": "Analyze what's on the user's screen",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        },
    ]

    steps = task_planner._fallback_plan("Search for weather forecast", simulated_tools)
    assert steps[0]["tool_name"] == "web_search"


@pytest.mark.asyncio
async def test_fallback_plan_no_match(task_planner: TaskPlanner) -> None:
    """Test fallback plan with no matching tools."""
    simulated_tools = [
        {
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": "Capture screenshot of screen",
                "parameters": {},
            },
        },
    ]

    steps = task_planner._fallback_plan("do something completely random xyzabc", simulated_tools)
    assert len(steps) >= 1
    assert steps[0].get("description")


@pytest.mark.asyncio
async def test_plan_with_llm_no_api_key(task_planner: TaskPlanner) -> None:
    """Test LLM planning returns None when no API key."""
    with patch("app.config.settings.openai_api_key", None):
        result = await task_planner._plan_with_llm("Test goal", [])
    assert result is None


@pytest.mark.asyncio
async def test_plan_with_llm_success(task_planner: TaskPlanner) -> None:
    """Test successful LLM plan generation."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"steps": ['
                '{"description": "Search for Python tutorials", '
                '"tool_name": "web_search", '
                '"tool_params": {"query": "Python"}},'
                '{"description": "Save results to file", '
                '"tool_name": "file_ops", '
                '"tool_params": {"operation": "write", "path": "/tmp/result.txt", "content": "done"}}'
                "]}",
            ),
        )
    ]

    simulated_tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "file_ops",
                "description": "File operations",
                "parameters": {},
            },
        },
    ]

    with patch.object(task_planner, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        with patch("app.config.settings.openai_api_key", "sk-test-key"):
            steps = await task_planner._plan_with_llm(
                "Find Python tutorials and save them", simulated_tools
            )

    assert steps is not None
    assert len(steps) == 2
    assert steps[0]["tool_name"] == "web_search"
    assert steps[1]["tool_name"] == "file_ops"


@pytest.mark.asyncio
async def test_plan_with_llm_invalid_json(task_planner: TaskPlanner) -> None:
    """Test LLM planning returns None when response is invalid JSON."""
    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content="This is not valid JSON at all",
            ),
        )
    ]

    with patch.object(task_planner, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        steps = await task_planner._plan_with_llm("Test goal", [])
    assert steps is None


@pytest.mark.asyncio
async def test_plan_with_llm_api_error(task_planner: TaskPlanner) -> None:
    """Test LLM planning returns None when API errors."""
    with patch.object(task_planner, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API rate limit"),
        )
        mock_get_client.return_value = mock_client

        steps = await task_planner._plan_with_llm("Test goal", [])
    assert steps is None


@pytest.mark.asyncio
async def test_generate_plan_with_db(
    task_planner: TaskPlanner,
    db_session: pytest.fixture,
) -> None:
    """Test generate_plan creates plan and steps in database."""
    import uuid

    user_id = uuid.uuid4()
    tools = task_planner._get_available_tools()

    # Mock LLM to use fallback
    with patch.object(task_planner, "_plan_with_llm", return_value=None):
        plan = await task_planner.generate_plan(
            goal="Test goal for database creation",
            db=db_session,
            user_id=user_id,
        )

    assert isinstance(plan, TaskPlan)
    assert plan.goal == "Test goal for database creation"
    assert plan.status == "pending"
    assert plan.user_id == user_id
    assert plan.id is not None


@pytest.mark.asyncio
async def test_generate_plan_creates_steps(
    task_planner: TaskPlanner,
    db_session: pytest.fixture,
) -> None:
    """Test that generate_plan creates steps in the database."""
    import uuid

    from sqlalchemy import select

    user_id = uuid.uuid4()

    # Mock LLM to return specific steps
    steps_data = [
        {
            "description": "Search the web",
            "tool_name": "web_search",
            "tool_params": {"query": "test"},
        },
    ]

    with patch.object(task_planner, "_plan_with_llm", return_value=steps_data):
        plan = await task_planner.generate_plan(
            goal="Search test",
            db=db_session,
            user_id=user_id,
        )

    # Verify steps were created
    result = await db_session.execute(
        select(TaskStep).where(TaskStep.plan_id == plan.id)
    )
    steps = result.scalars().all()
    assert len(steps) == 1
    assert steps[0].tool_name == "web_search"
    assert steps[0].description == "Search the web"


@pytest.mark.asyncio
async def test_generate_plan_fallback_creates_steps(
    task_planner: TaskPlanner,
    db_session: pytest.fixture,
) -> None:
    """Test fallback plan also creates steps in the database."""
    import uuid

    from sqlalchemy import select

    user_id = uuid.uuid4()

    # Force fallback by returning None from LLM
    with patch.object(task_planner, "_plan_with_llm", return_value=None):
        plan = await task_planner.generate_plan(
            goal="Find info about Python programming",
            db=db_session,
            user_id=user_id,
        )

    # Verify steps were created via fallback
    result = await db_session.execute(
        select(TaskStep).where(TaskStep.plan_id == plan.id)
    )
    steps = result.scalars().all()
    assert len(steps) >= 1


@pytest.mark.asyncio
async def test_generate_plan_with_llm_success(
    task_planner: TaskPlanner,
    db_session: pytest.fixture,
) -> None:
    """Test full pipeline: LLM plan → DB storage."""
    import uuid

    from sqlalchemy import select

    user_id = uuid.uuid4()

    mock_response = AsyncMock()
    mock_response.choices = [
        AsyncMock(
            message=AsyncMock(
                content='{"steps": ['
                '{"description": "Check what\'s on screen", '
                '"tool_name": "screen_vision", '
                '"tool_params": {"query": "describe the screen"}}'
                "]}",
            ),
        )
    ]

    with patch.object(task_planner, "_get_client") as mock_get_client:
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        with patch("app.config.settings.openai_api_key", "sk-test-key"):
            plan = await task_planner.generate_plan(
                goal="What's on my screen?",
                db=db_session,
                user_id=user_id,
            )

    assert plan.status == "pending"

    result = await db_session.execute(
        select(TaskStep).where(TaskStep.plan_id == plan.id)
    )
    steps = result.scalars().all()
    assert len(steps) == 1
    assert steps[0].tool_name == "screen_vision"


@pytest.mark.asyncio
async def test_singleton() -> None:
    """Test the singleton pattern works."""
    from app.services.task_planner import get_task_planner

    planner1 = get_task_planner()
    planner2 = get_task_planner()
    assert planner1 is planner2