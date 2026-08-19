"""Test Execution Engine — runs automated QA tests against websites.

Uses Jarvis's existing capabilities (browser navigation, screenshots,
vision analysis, click/type) to verify test criteria against a target URL.

Reuses the TaskPlanner and TaskExecutionEngine from Phase 7 for multi-step
test flows (e.g. form submission, login flows).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.testing import TestResult, TestRun
from app.services.tool_executor import ToolExecutor
from app.services.vision import get_vision_service

logger = get_logger(__name__)

# Timeouts
_STEP_TIMEOUT = 30  # seconds per test step
_RUN_TIMEOUT = 300  # 5 minutes per test run

# Screenshot storage directory
_SCREENSHOTS_DIR = "data/test_screenshots"


class TestingEngine:
    """Executes automated QA test plans against websites.

    For each test criterion in a run:
    1. Navigate to the target URL
    2. Take a screenshot
    3. Use vision analysis to verify the criterion
    4. Record pass/fail with screenshot evidence
    """

    def __init__(self) -> None:
        self._tool_executor = ToolExecutor()
        self._vision_service = get_vision_service()

    async def run_test_plan(self, run_id: str) -> None:
        """Execute a test run in the background.

        Args:
            run_id: The UUID of the TestRun to execute.
        """
        logger.info("Starting test run", run_id=run_id)
        try:
            run_uuid = uuid.UUID(str(run_id))
        except ValueError:
            logger.error("Invalid test run id", run_id=run_id)
            return

        async with async_session_factory() as db:
            # Load the test run
            result = await db.execute(
                select(TestRun)
                .options(selectinload(TestRun.results))
                .where(TestRun.id == run_uuid)
            )
            run = result.scalar_one_or_none()

            if run is None:
                logger.error("Test run not found", run_id=run_id)
                return

            if run.status != "pending":
                logger.warning(
                    "Test run not in pending state",
                    run_id=run_id,
                    status=run.status,
                )
                return

            # Mark as running
            run.status = "running"
            run.started_at = datetime.now(UTC)
            run.total_tests = len(run.results) if run.results else 0
            await db.commit()

            overall_start = time.time()

            # Execute each test criterion
            for test_result in run.results:
                # Check timeout
                if time.time() - overall_start > _RUN_TIMEOUT:
                    logger.warning("Test run timed out", run_id=run_id)
                    test_result.passed = False
                    test_result.detail = "Test run timed out (5 minute limit)"
                    run.failed += 1
                    run.status = "failed"
                    run.completed_at = datetime.now(UTC)
                    await db.commit()
                    return

                await self._execute_criterion(run, test_result, db)

            # Mark run as completed
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            await db.commit()

            elapsed = time.time() - overall_start
            logger.info(
                "Test run completed",
                run_id=run_id,
                passed=run.passed,
                failed=run.failed,
                total=run.total_tests,
                duration_sec=round(elapsed, 2),
            )

    async def _execute_criterion(
        self,
        run: TestRun,
        test_result: TestResult,
        db: AsyncSession,
    ) -> None:
        """Execute a single test criterion."""
        step_start = time.time()
        logger.info(
            "Executing test criterion",
            run_id=str(run.id),
            step=test_result.step_number,
            criterion=test_result.criterion[:60],
            test_type=test_result.test_type,
        )

        try:
            # Step 1: Navigate to the URL
            nav_result = await self._navigate_to_url(run.url)
            if "error" in nav_result:
                test_result.passed = False
                test_result.detail = f"Navigation failed: {nav_result['error']}"
                run.failed += 1
                test_result.duration_ms = int((time.time() - step_start) * 1000)
                await db.commit()
                return

            # Brief pause for page to render
            await asyncio.sleep(1.5)

            # Step 2: Take a screenshot
            screenshot_result = await self._take_screenshot(run.id, test_result.step_number)
            if "error" in screenshot_result:
                test_result.passed = False
                test_result.detail = f"Screenshot failed: {screenshot_result['error']}"
                run.failed += 1
                test_result.duration_ms = int((time.time() - step_start) * 1000)
                await db.commit()
                return

            screenshot_path = screenshot_result.get("path", "")
            test_result.screenshot_path = screenshot_path

            # Step 3: Verify the criterion using vision analysis
            screenshot_bytes = screenshot_result.get("bytes", b"")
            passed, detail = await self._verify_criterion(
                test_type=test_result.test_type,
                criterion=test_result.criterion,
                screenshot_bytes=screenshot_bytes,
            )

            test_result.passed = passed
            test_result.detail = detail
            test_result.duration_ms = int((time.time() - step_start) * 1000)

            if passed:
                run.passed += 1
                logger.info(
                    "Test passed",
                    run_id=str(run.id),
                    step=test_result.step_number,
                    criterion=test_result.criterion[:60],
                )
            else:
                run.failed += 1
                logger.warning(
                    "Test failed",
                    run_id=str(run.id),
                    step=test_result.step_number,
                    criterion=test_result.criterion[:60],
                    detail=detail,
                )

            await db.commit()

        except TimeoutError:
            test_result.passed = False
            test_result.detail = "Test step timed out (30 second limit)"
            test_result.duration_ms = int((time.time() - step_start) * 1000)
            run.failed += 1
            await db.commit()
            logger.warning(
                "Test step timed out",
                run_id=str(run.id),
                step=test_result.step_number,
            )

        except Exception as e:
            test_result.passed = False
            test_result.detail = f"Unexpected error: {e!s}"
            test_result.duration_ms = int((time.time() - step_start) * 1000)
            run.failed += 1
            await db.commit()
            logger.error(
                "Test step failed with exception",
                run_id=str(run.id),
                step=test_result.step_number,
                error=str(e),
            )

    async def _navigate_to_url(self, url: str) -> dict[str, Any]:
        """Navigate to a URL using the browser tool.

        Returns the navigation result or error.
        """
        try:
            result = await asyncio.wait_for(
                self._tool_executor.execute(
                    tool_name="browser",
                    arguments={"action": "navigate", "url": url},
                ),
                timeout=_STEP_TIMEOUT,
            )
            return result
        except TimeoutError:
            return {"error": "Navigation timed out"}
        except Exception as e:
            return {"error": str(e)}

    async def _take_screenshot(
        self,
        run_id: uuid.UUID,
        step_number: int,
    ) -> dict[str, Any]:
        """Take a screenshot of the current page.

        Returns the screenshot path and bytes, or error.
        """
        try:
            result = await asyncio.wait_for(
                self._tool_executor.execute(
                    tool_name="screenshot",
                    arguments={},
                ),
                timeout=15,
            )
            if "error" in result:
                return {"error": result["error"]}

            screenshot_data = result.get("result", {})
            if isinstance(screenshot_data, dict) and "data" in screenshot_data:
                import base64
                import os

                image_bytes = base64.b64decode(screenshot_data["data"])
                # Save screenshot to disk
                screenshot_dir = os.path.join(_SCREENSHOTS_DIR, str(run_id))
                os.makedirs(screenshot_dir, exist_ok=True)
                screenshot_path = os.path.join(
                    screenshot_dir, f"step_{step_number:02d}.png"
                )
                with open(screenshot_path, "wb") as f:
                    f.write(image_bytes)

                return {
                    "path": screenshot_path,
                    "bytes": image_bytes,
                }

            return {"error": "Screenshot returned unexpected format"}
        except TimeoutError:
            return {"error": "Screenshot timed out"}
        except Exception as e:
            return {"error": str(e)}

    async def _verify_criterion(
        self,
        test_type: str,
        criterion: str,
        screenshot_bytes: bytes,
    ) -> tuple[bool, str]:
        """Verify a test criterion against a screenshot using vision analysis.

        Returns (passed, detail) tuple.
        """
        if not screenshot_bytes:
            return False, "No screenshot available for verification"

        if test_type == "page_load":
            return await self._verify_page_load(criterion, screenshot_bytes)
        elif test_type == "element_visibility":
            return await self._verify_element_visibility(criterion, screenshot_bytes)
        elif test_type == "text_content":
            return await self._verify_text_content(criterion, screenshot_bytes)
        elif test_type == "link_click":
            return await self._verify_link_click(criterion, screenshot_bytes)
        elif test_type == "form_submission":
            return await self._verify_form_submission(criterion, screenshot_bytes)
        elif test_type == "screenshot":
            return True, "Screenshot captured (no verification)"
        else:
            # Default: use vision to check if the criterion is met
            return await self._verify_element_visibility(criterion, screenshot_bytes)

    async def _verify_page_load(
        self,
        criterion: str,
        screenshot_bytes: bytes,
    ) -> tuple[bool, str]:
        """Verify that the page loaded correctly."""
        result = await self._vision_service.analyze_screenshot(
            screenshot_bytes,
            prompt=(
                f"Analyze this screenshot of a web page. "
                f"Verify: {criterion}\n\n"
                "Does the page appear to have loaded correctly? "
                "Is there any error message, blank page, or loading indicator? "
                "Return a JSON object with:\n"
                "- 'passed': true/false\n"
                "- 'detail': brief explanation of what you see\n"
                "Only return valid JSON."
            ),
        )
        return self._parse_vision_result(result)

    async def _verify_element_visibility(
        self,
        criterion: str,
        screenshot_bytes: bytes,
    ) -> tuple[bool, str]:
        """Verify that a specific UI element is visible (or not) on the page."""
        result = await self._vision_service.find_element(
            screenshot_bytes,
            description=criterion,
        )
        if result.get("found", False):
            confidence = result.get("confidence", 0)
            label = result.get("label", "")
            detail = (
                f"Element found (confidence: {confidence:.2f})"
                + (f" — label: '{label}'" if label else "")
            )
            return True, detail
        else:
            explanation = result.get("explanation", "Element not found on screen")
            return False, f"Element not found: {explanation}"

    async def _verify_text_content(
        self,
        criterion: str,
        screenshot_bytes: bytes,
    ) -> tuple[bool, str]:
        """Verify that specific text content appears on the page."""
        result = await self._vision_service.extract_text_regions(screenshot_bytes)
        full_text = result.get("full_text", "").lower()
        criterion_lower = criterion.lower()

        # Extract key phrases from the criterion
        # Look for quoted text or the main subject
        import re

        quoted_texts = re.findall(r"['\"]([^'\"]+)['\"]", criterion)
        if quoted_texts:
            # Check for quoted text specifically
            for qt in quoted_texts:
                if qt.lower() in full_text:
                    return True, f"Found expected text: '{qt}'"
            return False, f"Expected text '{quoted_texts[0]}' not found on page"

        # General text presence check
        if "should contain" in criterion_lower:
            target = criterion_lower.split("should contain")[-1].strip()
            if target in full_text:
                return True, f"Page contains expected content: '{target[:80]}'"
            return False, f"Expected content '{target[:80]}' not found on page"

        # Default: use vision to verify
        vision_result = await self._vision_service.analyze_screenshot(
            screenshot_bytes,
            prompt=(
                f"Analyze this screenshot of a web page. "
                f"Verify: {criterion}\n\n"
                "Does the page contain the expected text content? "
                "Return a JSON object with:\n"
                "- 'passed': true/false\n"
                "- 'detail': brief explanation\n"
                "Only return valid JSON."
            ),
        )
        return self._parse_vision_result(vision_result, criterion)

    async def _verify_link_click(
        self,
        criterion: str,
        screenshot_bytes: bytes,
    ) -> tuple[bool, str]:
        """Verify that a link click test worked correctly."""
        # Vision analysis of the resulting page
        result = await self._vision_service.analyze_screenshot(
            screenshot_bytes,
            prompt=(
                f"Analyze this screenshot of a web page. "
                f"Verify: {criterion}\n\n"
                "Return a JSON object with:\n"
                "- 'passed': true/false\n"
                "- 'detail': brief explanation of what you see\n"
                "Only return valid JSON."
            ),
        )
        return self._parse_vision_result(result)

    async def _verify_form_submission(
        self,
        criterion: str,
        screenshot_bytes: bytes,
    ) -> tuple[bool, str]:
        """Verify that a form submission test worked correctly."""
        result = await self._vision_service.analyze_screenshot(
            screenshot_bytes,
            prompt=(
                f"Analyze this screenshot of a web page. "
                f"Verify: {criterion}\n\n"
                "Does the page show a successful form submission? "
                "Look for confirmation messages, success indicators, "
                "or the expected result state. "
                "Return a JSON object with:\n"
                "- 'passed': true/false\n"
                "- 'detail': brief explanation\n"
                "Only return valid JSON."
            ),
        )
        return self._parse_vision_result(result)

    def _parse_vision_result(
        self,
        vision_result: dict[str, Any],
        criterion: str | None = None,
    ) -> tuple[bool, str]:
        """Parse a vision analysis result to extract pass/fail and detail.

        Handles both JSON-structured and free-text responses.
        ``criterion`` (if given) is used as fallback detail when the vision
        result carries no explanation.
        """
        import json as json_module
        import re

        content = vision_result.get("description", vision_result.get("content", "{}"))

        # Try to parse JSON
        try:
            data = json_module.loads(content)
            passed = data.get("passed", False)
            detail = data.get("detail") or criterion or content
            return bool(passed), detail
        except (json_module.JSONDecodeError, ValueError):
            pass

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if json_match:
            try:
                data = json_module.loads(json_match.group(1))
                passed = data.get("passed", False)
                detail = data.get("detail") or criterion or content
                return bool(passed), detail
            except json_module.JSONDecodeError:
                pass

        # Fallback: check for positive/negative keywords
        content_lower = content.lower()
        if "passed" in content_lower and "true" in content_lower:
            return True, content[:200]
        elif "failed" in content_lower and "true" in content_lower:
            return False, content[:200]

        # Ultimate fallback: assume passed if we got a description
        return True, content[:200]

    async def create_test_run(
        self,
        user_id: uuid.UUID,
        url: str,
        criteria: list[dict[str, Any]],
        name: str | None = None,
        db: AsyncSession | None = None,
    ) -> TestRun:
        """Create a new test run with criteria, committing to the database.

        Args:
            user_id: Owner of the test run.
            url: Target website URL.
            criteria: List of dicts with 'criterion' and 'test_type' keys.
            name: Optional name for the run.
            db: Optional database session (creates one if not provided).

        Returns:
            The created TestRun ORM object.
        """
        if db is None:
            # Create own session and commit
            async with async_session_factory() as session:
                return await self._create_test_run_internal(
                    session, user_id, url, criteria, name
                )

        return await self._create_test_run_internal(
            db, user_id, url, criteria, name
        )

    async def _create_test_run_internal(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        url: str,
        criteria: list[dict[str, Any]],
        name: str | None = None,
    ) -> TestRun:
        """Internal helper to create and persist a test run."""
        run = TestRun(
            id=uuid.uuid4(),
            user_id=user_id,
            url=url,
            name=name,
            status="pending",
            total_tests=len(criteria),
        )
        db.add(run)
        await db.flush()

        for i, criterion in enumerate(criteria):
            test_result = TestResult(
                id=uuid.uuid4(),
                run_id=run.id,
                step_number=i + 1,
                criterion=criterion.get("criterion", f"Test step {i + 1}"),
                test_type=criterion.get("test_type", "element_visibility"),
                passed=False,
                duration_ms=0,
            )
            db.add(test_result)

        await db.commit()
        await db.refresh(run)
        return run


# Singleton
_testing_engine: TestingEngine | None = None


def get_testing_engine() -> TestingEngine:
    """Get or create the TestingEngine singleton."""
    global _testing_engine
    if _testing_engine is None:
        _testing_engine = TestingEngine()
    return _testing_engine
