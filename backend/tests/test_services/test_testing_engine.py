"""Tests for the TestingEngine service.

Tests the SaaS Testing Service execution engine, covering:
- Test run creation and status transitions
- Criterion execution with mocked browser/vision tools
- Error handling (timeouts, navigation failures, screenshot failures)
- Edge cases (empty criteria, invalid URLs, network errors)
- Vision result parsing
- Model CRUD and validation
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.testing import TestResult, TestRun

# ---------------------------------------------------------------------------
# Standalone test database setup
# (avoids importing app.main which has a pre-existing FreelanceJob conflict)
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite://"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_database() -> None:
    """Create tables before each test and drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session directly."""
    async with test_session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(monkeypatch: Any) -> Any:
    """Create a fresh TestingEngine for each test (no singleton).

    The engine opens its own session from the module-level
    ``async_session_factory`` bound to the real Postgres. For isolated unit
    tests we redirect that factory to the in-memory test DB so runs can see
    the rows created by the ``db_session`` fixture.
    """
    from app.services import testing_engine as testing_engine_module
    from tests.test_services.conftest_testing import test_session_factory
    monkeypatch.setattr(
        testing_engine_module, "async_session_factory", test_session_factory
    )
    from app.services.testing_engine import TestingEngine
    return TestingEngine()


@pytest.fixture
def sample_criteria() -> list[dict[str, str]]:
    """Sample test criteria for a test run."""
    return [
        {"criterion": "The login button should be visible", "test_type": "element_visibility"},
        {"criterion": "The page title should contain 'Welcome'", "test_type": "text_content"},
        {"criterion": "The page should load without errors", "test_type": "page_load"},
    ]


@pytest.fixture
def sample_url() -> str:
    """Sample URL for testing."""
    return "https://example.com"


# ---------------------------------------------------------------------------
# Helper: create a test run in the database
# ---------------------------------------------------------------------------


async def _create_test_run(
    db: AsyncSession,
    url: str = "https://example.com",
    criteria: list[dict[str, str]] | None = None,
    user_id: uuid.UUID | None = None,
    status: str = "pending",
) -> TestRun:
    """Helper to create a TestRun with TestResult rows."""
    if criteria is None:
        criteria = [{"criterion": "The page should load", "test_type": "page_load"}]
    if user_id is None:
        user_id = uuid.uuid4()

    run = TestRun(
        id=uuid.uuid4(),
        user_id=user_id,
        url=url,
        status=status,
        total_tests=len(criteria),
    )
    db.add(run)
    await db.flush()

    for i, c in enumerate(criteria):
        result = TestResult(
            id=uuid.uuid4(),
            run_id=run.id,
            step_number=i + 1,
            criterion=c.get("criterion", f"Step {i + 1}"),
            test_type=c.get("test_type", "element_visibility"),
            passed=False,
            duration_ms=0,
        )
        db.add(result)

    await db.commit()
    await db.refresh(run, ["results"])
    return run


# ---------------------------------------------------------------------------
# Tests: create_test_run
# ---------------------------------------------------------------------------


class TestCreateTestRun:
    """Tests for TestingEngine.create_test_run."""

    @pytest.mark.asyncio
    async def test_create_run_basic(
        self,
        engine: Any,
        db_session: AsyncSession,
        sample_url: str,
        sample_criteria: list[dict[str, str]],
    ) -> None:
        """Test basic test run creation with criteria."""
        user_id = uuid.uuid4()
        run = await engine.create_test_run(
            user_id=user_id,
            url=sample_url,
            criteria=sample_criteria,
            name="Smoke Test",
            db=db_session,
        )

        assert run.id is not None
        assert run.user_id == user_id
        assert run.url == sample_url
        assert run.name == "Smoke Test"
        assert run.status == "pending"
        assert run.total_tests == 3
        assert run.passed == 0
        assert run.failed == 0

        # Check results were created
        assert len(run.results) == 3
        assert run.results[0].step_number == 1
        assert run.results[0].criterion == sample_criteria[0]["criterion"]
        assert run.results[0].test_type == "element_visibility"

    @pytest.mark.asyncio
    async def test_create_run_empty_criteria(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test creating a run with empty criteria list."""
        user_id = uuid.uuid4()
        run = await engine.create_test_run(
            user_id=user_id,
            url="https://example.com",
            criteria=[],
            db=db_session,
        )

        assert run.total_tests == 0
        assert len(run.results) == 0
        assert run.status == "pending"

    @pytest.mark.asyncio
    async def test_create_run_name_default(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test that name is None when not provided."""
        user_id = uuid.uuid4()
        run = await engine.create_test_run(
            user_id=user_id,
            url="https://example.com",
            criteria=[{"criterion": "Test", "test_type": "page_load"}],
            db=db_session,
        )
        assert run.name is None


# ---------------------------------------------------------------------------
# Tests: run_test_plan (orchestrator)
# ---------------------------------------------------------------------------


class TestRunTestPlan:
    """Tests for TestingEngine.run_test_plan."""

    @pytest.mark.asyncio
    async def test_run_not_found(
        self,
        engine: Any,
    ) -> None:
        """Test that running a non-existent run_id logs an error and returns."""
        fake_id = str(uuid.uuid4())
        # Should not raise
        await engine.run_test_plan(fake_id)

    @pytest.mark.asyncio
    async def test_run_not_pending(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test that a run that's already running/completed is not re-executed."""
        run = await _create_test_run(db_session, status="completed")
        with patch.object(engine, "_tool_executor") as mock_executor:
            await engine.run_test_plan(str(run.id))
            mock_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_transitions_to_running(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test that a pending run transitions to 'running' when started."""
        run = await _create_test_run(db_session, criteria=[
            {"criterion": "Test", "test_type": "screenshot"},
        ])

        # Mock the navigation and screenshot to succeed
        with (
            patch.object(engine, "_navigate_to_url", return_value={"status": "ok"}),
            patch.object(engine, "_take_screenshot", return_value={
                "path": "/tmp/test.png",
                "bytes": b"fake_image_bytes",
            }),
            patch.object(engine, "_verify_criterion", return_value=(True, "Verified")),
        ):
            await engine.run_test_plan(str(run.id))

        # Reload the run
        result = await db_session.execute(select(TestRun).where(TestRun.id == run.id))
        updated_run = result.scalar_one()

        assert updated_run.status == "completed"
        assert updated_run.started_at is not None
        assert updated_run.completed_at is not None
        assert updated_run.passed == 1
        assert updated_run.failed == 0

    @pytest.mark.asyncio
    async def test_run_all_criteria_executed(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test that all criteria are executed during a run."""
        criteria = [
            {"criterion": "Step 1", "test_type": "screenshot"},
            {"criterion": "Step 2", "test_type": "screenshot"},
            {"criterion": "Step 3", "test_type": "screenshot"},
        ]
        run = await _create_test_run(db_session, criteria=criteria)

        executed_steps: list[str] = []

        async def track_nav(*args: Any, **kwargs: Any) -> dict[str, Any]:
            executed_steps.append("nav")
            return {"status": "ok"}

        async def track_screenshot(*args: Any, **kwargs: Any) -> dict[str, Any]:
            executed_steps.append("screenshot")
            return {"path": "/tmp/test.png", "bytes": b"data"}

        with (
            patch.object(engine, "_navigate_to_url", side_effect=track_nav),
            patch.object(engine, "_take_screenshot", side_effect=track_screenshot),
            patch.object(engine, "_verify_criterion", return_value=(True, "OK")),
        ):
            await engine.run_test_plan(str(run.id))

        # 3 criteria x (nav + screenshot) = 3 calls each
        assert executed_steps.count("nav") == 3
        assert executed_steps.count("screenshot") == 3

        result = await db_session.execute(select(TestRun).where(TestRun.id == run.id))
        updated_run = result.scalar_one()
        assert updated_run.status == "completed"
        assert updated_run.passed == 3
        assert updated_run.failed == 0


# ---------------------------------------------------------------------------
# Tests: _execute_criterion
# ---------------------------------------------------------------------------


class TestExecuteCriterion:
    """Tests for TestingEngine._execute_criterion."""

    @pytest.mark.asyncio
    async def test_criterion_navigation_failure(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test criterion failure when navigation fails."""
        run = await _create_test_run(db_session)
        test_result = run.results[0]

        with patch.object(engine, "_navigate_to_url", return_value={"error": "DNS lookup failed"}):
            await engine._execute_criterion(run, test_result, db_session)

        assert test_result.passed is False
        assert "Navigation failed" in (test_result.detail or "")
        assert test_result.duration_ms > 0
        assert run.failed == 1

    @pytest.mark.asyncio
    async def test_criterion_screenshot_failure(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test criterion failure when screenshot fails."""
        run = await _create_test_run(db_session)
        test_result = run.results[0]

        with (
            patch.object(engine, "_navigate_to_url", return_value={"status": "ok"}),
            patch.object(engine, "_take_screenshot", return_value={"error": "Screenshot failed"}),
        ):
            await engine._execute_criterion(run, test_result, db_session)

        assert test_result.passed is False
        assert "Screenshot failed" in (test_result.detail or "")
        assert run.failed == 1

    @pytest.mark.asyncio
    async def test_criterion_verification_fails(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test criterion failure when verification fails."""
        run = await _create_test_run(db_session)
        test_result = run.results[0]

        with (
            patch.object(engine, "_navigate_to_url", return_value={"status": "ok"}),
            patch.object(engine, "_take_screenshot", return_value={
                "path": "/tmp/test.png", "bytes": b"data",
            }),
            patch.object(engine, "_verify_criterion", return_value=(False, "Element not found")),
        ):
            await engine._execute_criterion(run, test_result, db_session)

        assert test_result.passed is False
        assert test_result.detail == "Element not found"
        assert run.failed == 1
        assert run.passed == 0

    @pytest.mark.asyncio
    async def test_criterion_verification_passes(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test criterion success when verification passes."""
        run = await _create_test_run(db_session)
        test_result = run.results[0]

        with (
            patch.object(engine, "_navigate_to_url", return_value={"status": "ok"}),
            patch.object(engine, "_take_screenshot", return_value={
                "path": "/tmp/test.png", "bytes": b"data",
            }),
            patch.object(engine, "_verify_criterion", return_value=(True, "Found element")),
        ):
            await engine._execute_criterion(run, test_result, db_session)

        assert test_result.passed is True
        assert test_result.detail == "Found element"
        assert run.passed == 1
        assert run.failed == 0
        assert test_result.screenshot_path == "/tmp/test.png"

    @pytest.mark.asyncio
    async def test_criterion_unexpected_exception(
        self,
        engine: Any,
        db_session: AsyncSession,
    ) -> None:
        """Test criterion handling of unexpected exceptions."""
        run = await _create_test_run(db_session)
        test_result = run.results[0]

        with patch.object(engine, "_navigate_to_url", side_effect=RuntimeError("Browser crashed")):
            await engine._execute_criterion(run, test_result, db_session)

        assert test_result.passed is False
        assert "Unexpected error" in (test_result.detail or "")
        assert run.failed == 1


# ---------------------------------------------------------------------------
# Tests: _navigate_to_url
# ---------------------------------------------------------------------------


class TestNavigateToUrl:
    """Tests for TestingEngine._navigate_to_url."""

    @pytest.mark.asyncio
    async def test_navigation_success(
        self,
        engine: Any,
    ) -> None:
        """Test successful navigation."""
        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(return_value={"status": "ok", "url": "https://example.com"})
            result = await engine._navigate_to_url("https://example.com")

        assert "error" not in result
        assert result["status"] == "ok"
        mock_executor.execute.assert_called_once_with(
            tool_name="browser",
            arguments={"action": "navigate", "url": "https://example.com"},
        )

    @pytest.mark.asyncio
    async def test_navigation_timeout(
        self,
        engine: Any,
    ) -> None:
        """Test navigation timeout."""
        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(side_effect=TimeoutError("Timed out"))
            result = await engine._navigate_to_url("https://example.com")

        assert "error" in result
        assert "timed out" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_navigation_exception(
        self,
        engine: Any,
    ) -> None:
        """Test navigation exception handling."""
        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(side_effect=ConnectionError("Connection refused"))
            result = await engine._navigate_to_url("https://example.com")

        assert "error" in result
        assert "Connection refused" in result["error"]


# ---------------------------------------------------------------------------
# Tests: _take_screenshot
# ---------------------------------------------------------------------------


class TestTakeScreenshot:
    """Tests for TestingEngine._take_screenshot."""

    @pytest.mark.asyncio
    async def test_screenshot_success(
        self,
        engine: Any,
    ) -> None:
        """Test successful screenshot capture."""
        import base64
        fake_image = b"fake_png_data"
        encoded = base64.b64encode(fake_image).decode()

        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(return_value={
                "result": {"data": encoded},
            })
            result = await engine._take_screenshot(
                run_id=uuid.uuid4(),
                step_number=1,
            )

        assert "error" not in result
        assert result["path"] is not None
        assert result["bytes"] == fake_image

    @pytest.mark.asyncio
    async def test_screenshot_error_from_tool(
        self,
        engine: Any,
    ) -> None:
        """Test screenshot when the tool returns an error."""
        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(return_value={"error": "No display available"})
            result = await engine._take_screenshot(
                run_id=uuid.uuid4(),
                step_number=1,
            )

        assert "error" in result
        assert "No display available" in result["error"]

    @pytest.mark.asyncio
    async def test_screenshot_unexpected_format(
        self,
        engine: Any,
    ) -> None:
        """Test screenshot when the tool returns unexpected format."""
        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(return_value={
                "result": "not_a_dict",
            })
            result = await engine._take_screenshot(
                run_id=uuid.uuid4(),
                step_number=1,
            )

        assert "error" in result
        assert "unexpected" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screenshot_timeout(
        self,
        engine: Any,
    ) -> None:
        """Test screenshot timeout."""
        with patch.object(engine, "_tool_executor") as mock_executor:
            mock_executor.execute = AsyncMock(side_effect=TimeoutError("Timed out"))
            result = await engine._take_screenshot(
                run_id=uuid.uuid4(),
                step_number=1,
            )

        assert "error" in result
        assert "timed out" in result["error"].lower()


# ---------------------------------------------------------------------------
# Tests: _verify_criterion (dispatch)
# ---------------------------------------------------------------------------


class TestVerifyCriterion:
    """Tests for TestingEngine._verify_criterion dispatch logic."""

    @pytest.mark.asyncio
    async def test_verify_no_screenshot(
        self,
        engine: Any,
    ) -> None:
        """Test verification with no screenshot bytes."""
        passed, detail = await engine._verify_criterion(
            test_type="page_load",
            criterion="Page should load",
            screenshot_bytes=b"",
        )
        assert passed is False
        assert "No screenshot" in detail

    @pytest.mark.asyncio
    async def test_verify_page_load(
        self,
        engine: Any,
    ) -> None:
        """Test page_load verification dispatch."""
        with patch.object(engine, "_verify_page_load", return_value=(True, "Page loaded")) as mock_method:
            passed, detail = await engine._verify_criterion(
                test_type="page_load",
                criterion="Page should load",
                screenshot_bytes=b"fake",
            )
        assert passed is True
        mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_element_visibility(
        self,
        engine: Any,
    ) -> None:
        """Test element_visibility verification dispatch."""
        with patch.object(engine, "_verify_element_visibility", return_value=(True, "Found")) as mock_method:
            passed, detail = await engine._verify_criterion(
                test_type="element_visibility",
                criterion="Button should be visible",
                screenshot_bytes=b"fake",
            )
        assert passed is True
        mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_text_content(
        self,
        engine: Any,
    ) -> None:
        """Test text_content verification dispatch."""
        with patch.object(engine, "_verify_text_content", return_value=(True, "Text found")) as mock_method:
            passed, detail = await engine._verify_criterion(
                test_type="text_content",
                criterion="Page should contain 'Welcome'",
                screenshot_bytes=b"fake",
            )
        assert passed is True
        mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_link_click(
        self,
        engine: Any,
    ) -> None:
        """Test link_click verification dispatch."""
        with patch.object(engine, "_verify_link_click", return_value=(True, "Link worked")) as mock_method:
            passed, detail = await engine._verify_criterion(
                test_type="link_click",
                criterion="Clicking login should work",
                screenshot_bytes=b"fake",
            )
        assert passed is True
        mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_form_submission(
        self,
        engine: Any,
    ) -> None:
        """Test form_submission verification dispatch."""
        with patch.object(engine, "_verify_form_submission", return_value=(True, "Form submitted")) as mock_method:
            passed, detail = await engine._verify_criterion(
                test_type="form_submission",
                criterion="Form should submit",
                screenshot_bytes=b"fake",
            )
        assert passed is True
        mock_method.assert_called_once()

    @pytest.mark.asyncio
    async def test_verify_screenshot_type(
        self,
        engine: Any,
    ) -> None:
        """Test screenshot type always passes without verification."""
        passed, detail = await engine._verify_criterion(
            test_type="screenshot",
            criterion="Capture screenshot",
            screenshot_bytes=b"fake",
        )
        assert passed is True
        assert "Screenshot captured" in detail

    @pytest.mark.asyncio
    async def test_verify_unknown_type_defaults(
        self,
        engine: Any,
    ) -> None:
        """Test unknown test type falls back to element_visibility."""
        with patch.object(engine, "_verify_element_visibility", return_value=(True, "Default fallback")) as mock_method:
            passed, detail = await engine._verify_criterion(
                test_type="unknown_type",
                criterion="Something should work",
                screenshot_bytes=b"fake",
            )
        assert passed is True
        mock_method.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _verify_page_load
# ---------------------------------------------------------------------------


class TestVerifyPageLoad:
    """Tests for TestingEngine._verify_page_load."""

    @pytest.mark.asyncio
    async def test_page_load_success(
        self,
        engine: Any,
    ) -> None:
        """Test page load verification passes."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.analyze_screenshot = AsyncMock(return_value={
                "description": '{"passed": true, "detail": "Page loaded successfully"}',
            })
            passed, detail = await engine._verify_page_load(
                "Page should load without errors",
                b"fake_bytes",
            )
        assert passed is True
        mock_vision.analyze_screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_load_failure(
        self,
        engine: Any,
    ) -> None:
        """Test page load verification fails."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.analyze_screenshot = AsyncMock(return_value={
                "description": '{"passed": false, "detail": "Page shows 404 error"}',
            })
            passed, detail = await engine._verify_page_load(
                "Page should load without errors",
                b"fake_bytes",
            )
        assert passed is False
        assert "404" in detail


# ---------------------------------------------------------------------------
# Tests: _verify_element_visibility
# ---------------------------------------------------------------------------


class TestVerifyElementVisibility:
    """Tests for TestingEngine._verify_element_visibility."""

    @pytest.mark.asyncio
    async def test_element_found(
        self,
        engine: Any,
    ) -> None:
        """Test element found by vision."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.find_element = AsyncMock(return_value={
                "found": True,
                "confidence": 0.95,
                "label": "Login Button",
                "x": 100,
                "y": 200,
            })
            passed, detail = await engine._verify_element_visibility(
                "The login button should be visible",
                b"fake_bytes",
            )
        assert passed is True
        assert "Element found" in detail
        assert "0.95" in detail

    @pytest.mark.asyncio
    async def test_element_not_found(
        self,
        engine: Any,
    ) -> None:
        """Test element not found by vision."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.find_element = AsyncMock(return_value={
                "found": False,
                "confidence": 0.0,
                "explanation": "Could not find the element on screen",
            })
            passed, detail = await engine._verify_element_visibility(
                "The non-existent element should be visible",
                b"fake_bytes",
            )
        assert passed is False
        assert "Element not found" in detail


# ---------------------------------------------------------------------------
# Tests: _verify_text_content
# ---------------------------------------------------------------------------


class TestVerifyTextContent:
    """Tests for TestingEngine._verify_text_content."""

    @pytest.mark.asyncio
    async def test_text_content_quoted_found(
        self,
        engine: Any,
    ) -> None:
        """Test text content with quoted text found."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.extract_text_regions = AsyncMock(return_value={
                "full_text": "Welcome to our website! Please log in.",
                "regions": [],
            })
            passed, detail = await engine._verify_text_content(
                "The page should contain 'Welcome'",
                b"fake_bytes",
            )
        assert passed is True
        assert "Found expected text" in detail

    @pytest.mark.asyncio
    async def test_text_content_quoted_not_found(
        self,
        engine: Any,
    ) -> None:
        """Test text content with quoted text not found."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.extract_text_regions = AsyncMock(return_value={
                "full_text": "Goodbye! See you later.",
                "regions": [],
            })
            passed, detail = await engine._verify_text_content(
                "The page should contain 'Welcome'",
                b"fake_bytes",
            )
        assert passed is False
        assert "not found" in detail

    @pytest.mark.asyncio
    async def test_text_content_should_contain_found(
        self,
        engine: Any,
    ) -> None:
        """Test text content with 'should contain' pattern found."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.extract_text_regions = AsyncMock(return_value={
                "full_text": "Welcome to our website!",
                "regions": [],
            })
            passed, detail = await engine._verify_text_content(
                "The page should contain Welcome",
                b"fake_bytes",
            )
        assert passed is True
        assert "contains expected content" in detail

    @pytest.mark.asyncio
    async def test_text_content_should_contain_not_found(
        self,
        engine: Any,
    ) -> None:
        """Test text content with 'should contain' pattern not found."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.extract_text_regions = AsyncMock(return_value={
                "full_text": "Goodbye!",
                "regions": [],
            })
            passed, detail = await engine._verify_text_content(
                "The page should contain Welcome",
                b"fake_bytes",
            )
        assert passed is False
        assert "not found" in detail

    @pytest.mark.asyncio
    async def test_text_content_default_vision_fallback(
        self,
        engine: Any,
    ) -> None:
        """Test text content falls back to vision analysis for generic criteria."""
        with patch.object(engine, "_vision_service") as mock_vision:
            mock_vision.extract_text_regions = AsyncMock(return_value={
                "full_text": "Some text on the page",
                "regions": [],
            })
            mock_vision.analyze_screenshot = AsyncMock(return_value={
                "description": '{"passed": true, "detail": "Text content verified"}',
            })
            passed, detail = await engine._verify_text_content(
                "Verify the page looks correct",
                b"fake_bytes",
            )
        assert passed is True
        mock_vision.analyze_screenshot.assert_called_once()


# ---------------------------------------------------------------------------
# Tests: _parse_vision_result
# ---------------------------------------------------------------------------


class TestParseVisionResult:
    """Tests for TestingEngine._parse_vision_result."""

    def test_parse_json_object(self, engine: Any) -> None:
        """Test parsing a JSON vision result."""
        result = {"description": '{"passed": true, "detail": "All good"}'}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is True
        assert detail == "All good"

    def test_parse_json_failed(self, engine: Any) -> None:
        """Test parsing a JSON failed result."""
        result = {"description": '{"passed": false, "detail": "Element missing"}'}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is False
        assert detail == "Element missing"

    def test_parse_markdown_code_block(self, engine: Any) -> None:
        """Test parsing JSON from a markdown code block."""
        result = {
            "description": (
                "Here is my analysis:\n"
                '```json\n{"passed": true, "detail": "Page loaded fine"}\n'
                "```\n"
            )
        }
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is True
        assert "Page loaded fine" in detail

    def test_parse_keyword_passed_true(self, engine: Any) -> None:
        """Test fallback keyword parsing for 'passed: true'."""
        result = {"description": "I can see the page. Passed: true. The page loaded correctly."}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is True

    def test_parse_keyword_failed_true(self, engine: Any) -> None:
        """Test fallback keyword parsing for 'failed: true'."""
        result = {"description": "Failed: true. The element is not visible on screen."}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is False

    def test_parse_ultimate_fallback(self, engine: Any) -> None:
        """Test ultimate fallback (assume passed)."""
        result = {"description": "I see a page with a blue background and some text."}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is True
        assert "I see a page" in detail

    def test_parse_uses_content_field(self, engine: Any) -> None:
        """Test parsing uses 'content' field when 'description' is absent."""
        result = {"content": '{"passed": false, "detail": "Error on page"}'}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert passed is False
        assert "Error" in detail

    def test_parse_overly_long_detail_truncated(self, engine: Any) -> None:
        """Test that detail is truncated to 200 chars in fallback mode."""
        long_text = "x" * 500
        result = {"description": long_text}
        passed, detail = engine._parse_vision_result(result, "Test criterion")
        assert len(detail) <= 200


# ---------------------------------------------------------------------------
# Tests: singleton getter
# ---------------------------------------------------------------------------


class TestGetTestingEngine:
    """Tests for the get_testing_engine singleton."""

    def test_singleton(self) -> None:
        """Test that get_testing_engine returns the same instance."""
        from app.services.testing_engine import TestingEngine, get_testing_engine, _testing_engine

        # Reset the singleton
        _testing_engine = None  # noqa: F841

        engine1 = get_testing_engine()
        engine2 = get_testing_engine()
        assert engine1 is engine2

    def test_creates_new_if_none(self) -> None:
        """Test that get_testing_engine creates a new instance if None."""
        from app.services.testing_engine import TestingEngine, get_testing_engine

        engine = get_testing_engine()
        assert isinstance(engine, TestingEngine)


# ---------------------------------------------------------------------------
# Tests: Model-level validation
# ---------------------------------------------------------------------------


class TestTestRunModel:
    """Tests for the TestRun ORM model."""

    @pytest.mark.asyncio
    async def test_create_test_run_model(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test creating a TestRun directly."""
        run_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(UTC)

        run = TestRun(
            id=run_id,
            user_id=user_id,
            url="https://example.com",
            name="My Test",
            status="pending",
            total_tests=2,
            passed=0,
            failed=0,
            created_at=now,
            updated_at=now,
        )
        db_session.add(run)
        await db_session.commit()

        # Verify stored correctly
        result = await db_session.execute(select(TestRun).where(TestRun.id == run_id))
        stored = result.scalar_one()
        assert stored.id == run_id
        assert stored.user_id == user_id
        assert stored.url == "https://example.com"
        assert stored.name == "My Test"
        assert stored.status == "pending"
        assert stored.passed == 0
        assert stored.failed == 0
        assert stored.total_tests == 2

    @pytest.mark.asyncio
    async def test_test_run_status_transitions(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test that status field can be updated."""
        run = await _create_test_run(db_session, status="pending")
        assert run.status == "pending"

        run.status = "running"
        run.started_at = datetime.now(UTC)
        await db_session.commit()

        result = await db_session.execute(select(TestRun).where(TestRun.id == run.id))
        updated = result.scalar_one()
        assert updated.status == "running"
        assert updated.started_at is not None

        updated.status = "completed"
        updated.completed_at = datetime.now(UTC)
        await db_session.commit()

        result = await db_session.execute(select(TestRun).where(TestRun.id == run.id))
        final = result.scalar_one()
        assert final.status == "completed"
        assert final.completed_at is not None

    @pytest.mark.asyncio
    async def test_test_run_cascade_delete(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test that deleting a TestRun cascades to its TestResults."""
        run = await _create_test_run(db_session, criteria=[
            {"criterion": "Test 1", "test_type": "page_load"},
            {"criterion": "Test 2", "test_type": "screenshot"},
        ])

        # Verify results exist
        assert len(run.results) == 2

        # Delete the run
        await db_session.delete(run)
        await db_session.commit()

        # Verify results are also deleted
        from sqlalchemy import func

        result = await db_session.execute(
            select(func.count()).select_from(TestResult)
            .where(TestResult.run_id == run.id)
        )
        count = result.scalar()
        assert count == 0

    @pytest.mark.asyncio
    async def test_test_run_default_values(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test TestRun default values."""
        run = TestRun(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            url="https://example.com",
        )
        db_session.add(run)
        await db_session.commit()

        assert run.status == "pending"
        assert run.total_tests == 0
        assert run.passed == 0
        assert run.failed == 0
        assert run.name is None
        assert run.report_path is None
        assert run.started_at is None
        assert run.completed_at is None
        assert run.created_at is not None
        assert run.updated_at is not None

    @pytest.mark.asyncio
    async def test_test_result_defaults(
        self,
        db_session: AsyncSession,
    ) -> None:
        """Test TestResult default values."""
        run = await _create_test_run(db_session, criteria=[
            {"criterion": "Test", "test_type": "page_load"},
        ])
        result = run.results[0]

        assert result.passed is False
        assert result.duration_ms == 0
        assert result.screenshot_path is None
        assert result.detail is None
        assert result.created_at is not None


# ---------------------------------------------------------------------------
# Tests: AsyncGenerator import for type hint
# ---------------------------------------------------------------------------

# Import needed for the fixture type hint
try:
    from collections.abc import AsyncGenerator  # noqa: F401
except ImportError:
    pass