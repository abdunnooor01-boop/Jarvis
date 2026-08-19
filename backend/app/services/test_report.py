"""Test Report Generator — generates human-readable HTML test reports.

Takes a completed TestRun and produces a standalone HTML report file
with pass/fail summary, per-test results with screenshots, and metadata.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.testing import TestRun

logger = get_logger(__name__)

_REPORTS_DIR = "data/test_reports"


class TestReportGenerator:
    """Generates HTML test reports from completed TestRun data."""

    async def generate_report(
        self,
        run_id: str,
        db: AsyncSession | None = None,
    ) -> str | None:
        """Generate an HTML report for a test run.

        Args:
            run_id: The UUID of the TestRun to report on.
            db: Optional database session.

        Returns:
            The file path to the generated report, or None on failure.
        """
        if db is None:
            async with async_session_factory() as session:
                return await self._generate_report_internal(session, run_id)

        return await self._generate_report_internal(db, run_id)

    async def _generate_report_internal(
        self,
        db: AsyncSession,
        run_id: str,
    ) -> str | None:
        """Internal helper to generate the report."""
        run_uuid = uuid.UUID(str(run_id))
        result = await db.execute(
            select(TestRun).where(TestRun.id == run_uuid)
        )
        run = result.scalar_one_or_none()

        if run is None:
            logger.error("Test run not found for report generation", run_id=run_id)
            return None

        # Calculate duration
        duration_str = "N/A"
        if run.started_at and run.completed_at:
            duration_sec = (run.completed_at - run.started_at).total_seconds()
            if duration_sec < 60:
                duration_str = f"{duration_sec:.1f}s"
            else:
                duration_str = f"{duration_sec / 60:.1f}m {duration_sec % 60:.0f}s"

        # Calculate pass rate
        pass_rate = 0
        if run.total_tests > 0:
            pass_rate = round((run.passed / run.total_tests) * 100)

        # Build template context
        context = {
            "title": f"Test Report: {run.name or 'Untitled Run'}",
            "url": run.url,
            "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "duration": duration_str,
            "status": run.status.capitalize(),
            "total": run.total_tests,
            "passed": run.passed,
            "failed": run.failed,
            "pass_rate": pass_rate,
            "results": [
                {
                    "step_number": r.step_number,
                    "criterion": r.criterion,
                    "test_type": r.test_type,
                    "passed": r.passed,
                    "detail": r.detail or "",
                    "duration_ms": r.duration_ms,
                    "screenshot_path": (
                        self._make_relative_path(r.screenshot_path)
                        if r.screenshot_path else None
                    ),
                }
                for r in (run.results or [])
            ],
        }

        # Render the template
        html = self._render_template(context)

        # Write the report file
        os.makedirs(_REPORTS_DIR, exist_ok=True)
        report_filename = f"test_report_{run_id}.html"
        report_path = os.path.join(_REPORTS_DIR, report_filename)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Update the run's report_path
        run.report_path = report_path
        await db.commit()

        logger.info(
            "Test report generated",
            run_id=run_id,
            path=report_path,
        )

        return report_path

    def _make_relative_path(self, absolute_path: str) -> str:
        """Convert an absolute path to a relative path for HTML embedding."""
        # Try to make it relative to the reports directory
        try:
            return os.path.relpath(absolute_path, _REPORTS_DIR)
        except ValueError:
            return absolute_path

    def _render_template(self, context: dict[str, Any]) -> str:
        """Render the HTML template with the given context.

        Uses simple string replacement (no Jinja2 dependency) to keep
        the project lightweight. Supports basic variable substitution
        and a simple {% for %} loop.
        """
        import os as _os

        template_path = _os.path.join(
            _os.path.dirname(__file__), "..", "templates", "test_report.html"
        )
        with open(template_path, encoding="utf-8") as f:
            template = f.read()

        # Replace simple variables
        html = template
        for key, value in context.items():
            if key == "results":
                continue  # Handled separately
            placeholder = "{{ " + key + " }}"
            html = html.replace(placeholder, str(value))

        # Handle the {% for result in results %} loop
        results_block_start = "{% for result in results %}"
        results_block_end = "{% endfor %}"
        start_idx = html.find(results_block_start)
        end_idx = html.find(results_block_end)

        if start_idx != -1 and end_idx != -1:
            template_block = html[start_idx + len(results_block_start):end_idx]
            rendered_results = []

            for result in context.get("results", []):
                item_html = template_block
                for key, value in result.items():
                    placeholder = "{{ result." + key + " }}"
                    item_html = item_html.replace(placeholder, str(value))
                # Handle conditional blocks
                # {% if result.passed %} ... {% else %} ... {% endif %}
                item_html = self._render_conditionals(item_html, result)
                rendered_results.append(item_html)

            html = (
                html[:start_idx]
                + "".join(rendered_results)
                + html[end_idx + len(results_block_end):]
            )

        # Handle remaining conditionals in the outer template
        html = self._render_conditionals(html, context)

        return html

    def _render_conditionals(self, html: str, context: dict[str, Any]) -> str:
        """Render {% if %} and {% else %} blocks based on context values.

        Supports simple truthy/falsy checks on top-level keys and
        result.passed for the results loop.
        """
        import re

        def _eval_condition(condition: str) -> bool:
            """Evaluate a simple condition string like 'result.passed'."""
            condition = condition.strip()
            if condition.startswith("result."):
                key = condition[7:]
                return bool(context.get(key, False))
            return bool(context.get(condition, False))

        # Process {% if %} ... {% else %} ... {% endif %}
        pattern = r"{% if\s+([^%]+)\s*%}(.*?){% else %}(.*?){% endif %}"
        while re.search(pattern, html, re.DOTALL):
            match = re.search(pattern, html, re.DOTALL)
            if match:
                condition = match.group(1).strip()
                if_true = match.group(2)
                if_false = match.group(3)
                replacement = if_true if _eval_condition(condition) else if_false
                html = html[:match.start()] + replacement + html[match.end():]

        # Process {% if %} ... {% endif %} (no else)
        pattern = r"{% if\s+([^%]+)\s*%}(.*?){% endif %}"
        while re.search(pattern, html, re.DOTALL):
            match = re.search(pattern, html, re.DOTALL)
            if match:
                condition = match.group(1).strip()
                content = match.group(2)
                replacement = content if _eval_condition(condition) else ""
                html = html[:match.start()] + replacement + html[match.end():]

        return html


# Singleton
_report_generator: TestReportGenerator | None = None


def get_report_generator() -> TestReportGenerator:
    """Get or create the TestReportGenerator singleton."""
    global _report_generator
    if _report_generator is None:
        _report_generator = TestReportGenerator()
    return _report_generator
