"""Freelance Delivery System — packages and delivers job results.

This module handles the final delivery phase of a freelance job:
1. Packages all artifacts into a deliverables directory
2. Generates a summary report
3. Marks the job as delivered
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from app.api.ws import manager as ws_manager
from app.core.logging import get_logger
from app.database import async_session_factory
from app.models.freelance_job import FreelanceJob

logger = get_logger(__name__)

# Base directory for deliverables
DELIVERABLES_BASE = Path("data/deliverables")


def _ensure_deliverables_dir() -> Path:
    """Ensure the deliverables base directory exists."""
    DELIVERABLES_BASE.mkdir(parents=True, exist_ok=True)
    return DELIVERABLES_BASE


async def deliver_results(job_id: str, user_id: str) -> bool:
    """Package and deliver the results of a completed freelance job.

    Args:
        job_id: The UUID of the FreelanceJob to deliver.
        user_id: The UUID of the user who owns the job.

    Returns:
        True if delivery was successful, False otherwise.
    """
    logger.info("Delivering freelance job results", job_id=job_id)

    async with async_session_factory() as db:
        result = await db.execute(
            select(FreelanceJob).where(FreelanceJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if job is None:
            logger.error("Freelance job not found", job_id=job_id)
            return False

        if job.status != "completed":
            logger.warning(
                "Job not in completed state",
                job_id=job_id,
                status=job.status,
            )
            return False

        try:
            # Create a unique deliverable directory
            base = _ensure_deliverables_dir()
            deliverable_dir = base / (
                f"{job_id}_{job.task_type}_"
                f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            )
            deliverable_dir.mkdir(parents=True, exist_ok=True)

            # Copy result files into the deliverable directory
            copied_files = _copy_result_files(job, deliverable_dir)

            # Generate a summary report
            report_path = _generate_summary_report(job, deliverable_dir)

            # Mark job as delivered
            job.status = "delivered"
            job.deliverable_path = str(deliverable_dir)
            job.delivered_at = datetime.now(UTC)
            await db.commit()

            # Send WebSocket notification
            await ws_manager.send_json(user_id, {
                "type": "job_delivered",
                "job_id": job_id,
                "deliverable_path": str(deliverable_dir),
                "report_path": str(report_path),
                "file_count": len(copied_files),
            })

            logger.info(
                "Job delivered successfully",
                job_id=job_id,
                path=str(deliverable_dir),
                files=len(copied_files),
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to deliver job",
                job_id=job_id,
                error=str(e),
            )

            # Mark as failed delivery
            job.error = f"Delivery failed: {e}"
            await db.commit()
            return False


def _copy_result_files(job: FreelanceJob, dest_dir: Path) -> list[str]:
    """Copy result files from the job into the deliverable directory.

    Returns a list of copied file paths (relative to dest_dir).
    """
    copied_files: list[str] = []

    if not job.result_files:
        return copied_files

    for file_path in job.result_files:
        src = Path(file_path)
        if src.exists() and src.is_file():
            try:
                dest = dest_dir / src.name
                shutil.copy2(src, dest)
                copied_files.append(str(dest))
                logger.info("Copied result file", src=str(src), dest=str(dest))
            except Exception as e:
                logger.warning(
                    "Failed to copy result file",
                    src=str(src),
                    error=str(e),
                )

    return copied_files


def _generate_summary_report(job: FreelanceJob, dest_dir: Path) -> Path:
    """Generate a human-readable summary report for the job.

    Returns the path to the generated report file.
    """
    report_lines: list[str] = [
        "=" * 60,
        "  JARVIS FREELANCE JOB REPORT",
        "=" * 60,
        "",
        f"Job ID:       {job.id}",
        f"Title:        {job.title}",
        f"Task Type:    {job.task_type}",
        f"Status:       {job.status}",
        f"Price:        ${job.price:.2f}" if job.price else "Price:         N/A",
        "",
        "-" * 60,
        "  DESCRIPTION",
        "-" * 60,
        "",
        job.description,
        "",
    ]

    if job.result_summary:
        report_lines.extend([
            "-" * 60,
            "  RESULTS",
            "-" * 60,
            "",
            job.result_summary,
            "",
        ])

    if job.result_files:
        report_lines.extend([
            "-" * 60,
            "  DELIVERABLES",
            "-" * 60,
            "",
        ])
        for f in job.result_files:
            report_lines.append(f"  - {f}")

    report_lines.extend([
        "",
        "-" * 60,
        f"  Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 60,
    ])

    report_path = dest_dir / "summary_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    logger.info("Summary report generated", path=str(report_path))
    return report_path
