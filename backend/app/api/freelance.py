"""Freelance API — task catalog, order management, and Stripe payment integration."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.database import get_db
from app.models.freelance_task import FreelanceJob, TaskTemplate
from app.models.user import User
from app.schemas.freelance_task import (
    FreelanceJobListResponse,
    FreelanceJobResponse,
    OrderCreateRequest,
    OrderCreateResponse,
    TaskTemplateListResponse,
    TaskTemplateResponse,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/freelance", tags=["freelance"])

# Pre-seeded task templates
_SEED_TEMPLATES = [
    {
        "name": "App Testing",
        "description": "Comprehensive manual testing of your web or mobile application. Includes functional testing, UI/UX review, and bug reports with screenshots.",
        "category": "testing",
        "price_cents": 1000,  # $10
        "estimated_minutes": 60,
        "required_capabilities": ["screen_vision", "browser_control", "file_ops"],
    },
    {
        "name": "Copywriting",
        "description": "Professional copywriting for your website, landing page, or marketing materials. Delivered per page with revisions included.",
        "category": "writing",
        "price_cents": 500,  # $5
        "estimated_minutes": 30,
        "required_capabilities": ["file_ops", "web_search"],
    },
    {
        "name": "Data Entry",
        "description": "Accurate data entry and data processing. Extract, organize, and format data from documents, spreadsheets, or websites.",
        "category": "data",
        "price_cents": 800,  # $8
        "estimated_minutes": 45,
        "required_capabilities": ["file_ops", "web_search", "clipboard"],
    },
    {
        "name": "Web Research",
        "description": "In-depth web research on any topic. Gathers information from multiple sources, verifies facts, and compiles a comprehensive report.",
        "category": "research",
        "price_cents": 1200,  # $12
        "estimated_minutes": 60,
        "required_capabilities": ["web_search", "file_ops"],
    },
    {
        "name": "Content Writing",
        "description": "Well-researched content writing for blogs, articles, and social media. SEO-optimized with proper citations.",
        "category": "writing",
        "price_cents": 1500,  # $15
        "estimated_minutes": 90,
        "required_capabilities": ["web_search", "file_ops"],
    },
    {
        "name": "Form Filling",
        "description": "Automated form filling and submission. Handles online forms, applications, registrations with accurate data entry.",
        "category": "data",
        "price_cents": 600,  # $6
        "estimated_minutes": 20,
        "required_capabilities": ["browser_control", "clipboard", "keyboard"],
    },
    {
        "name": "File Processing",
        "description": "Process, convert, and organize files. Supports PDF, images, documents, spreadsheets, and text files with format conversion.",
        "category": "data",
        "price_cents": 700,  # $7
        "estimated_minutes": 30,
        "required_capabilities": ["file_ops", "screen_vision"],
    },
    {
        "name": "Email Drafting",
        "description": "Professional email drafting for business correspondence, customer support, outreach, and follow-ups. Customizable tone and style.",
        "category": "writing",
        "price_cents": 400,  # $4
        "estimated_minutes": 15,
        "required_capabilities": ["file_ops"],
    },
]

# Price tiers for free-form requests (cents)
_FREEFORM_PRICES = {
    "simple": 500,    # $5
    "medium": 1000,   # $10
    "complex": 2500,  # $25
}

_ESTIMATION_SYSTEM_PROMPT = """You are Jarvis's price estimation system. Given a user's task description, estimate its complexity.

Classify the task into one of three tiers:
- "simple": Quick, single-step tasks (e.g., draft an email, fill one form, simple copywriting)
- "medium": Multi-step tasks requiring planning (e.g., test a web app, research a topic, content writing)
- "complex": Complex multi-step tasks requiring deep planning (e.g., full QA suite, data pipeline, multi-page content)

Return ONLY valid JSON with this structure:
{"complexity": "simple|medium|complex", "reason": "brief one-sentence explanation"}"""


def _cents_to_dollars(cents: int) -> float:
    """Convert cents to dollars."""
    return round(cents / 100.0, 2)


async def _ensure_templates_seeded(db: AsyncSession) -> None:
    """Seed task templates if they don't exist yet."""
    result = await db.execute(select(func.count(TaskTemplate.id)))
    count = result.scalar() or 0
    if count > 0:
        return

    logger.info("Seeding freelance task templates", count=len(_SEED_TEMPLATES))
    for tpl in _SEED_TEMPLATES:
        template = TaskTemplate(
            id=uuid.uuid4(),
            name=tpl["name"],
            description=tpl["description"],
            category=tpl["category"],
            price_cents=tpl["price_cents"],
            estimated_minutes=tpl["estimated_minutes"],
            required_capabilities=tpl["required_capabilities"],
            is_active=True,
        )
        db.add(template)
    await db.commit()


async def _get_stripe_client() -> Any:
    """Get or create the Stripe client."""
    import stripe

    stripe.api_key = settings.stripe_secret_key or "sk_test_placeholder"
    return stripe


def _template_to_response(t: TaskTemplate) -> TaskTemplateResponse:
    """Convert a TaskTemplate ORM to response schema."""
    return TaskTemplateResponse(
        id=t.id,
        name=t.name,
        description=t.description,
        category=t.category,
        price_cents=t.price_cents,
        price_dollars=_cents_to_dollars(t.price_cents),
        estimated_minutes=t.estimated_minutes,
        required_capabilities=t.required_capabilities or [],
        is_active=t.is_active,
    )


async def _estimate_price(description: str) -> tuple[int, str]:
    """Estimate a price for a free-form task description using the LLM.

    Returns (price_cents, complexity_label).
    Falls back to medium ($10) if LLM is unavailable or fails.
    """
    if not settings.openai_api_key:
        logger.info("No OpenAI key — using default price for free-form request")
        return _FREEFORM_PRICES["medium"], "medium"

    try:
        import openai

        client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": _ESTIMATION_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task description: {description}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=256,
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)
        complexity = data.get("complexity", "medium")
        if complexity not in _FREEFORM_PRICES:
            complexity = "medium"

        logger.info(
            "Free-form price estimated",
            complexity=complexity,
            price_cents=_FREEFORM_PRICES[complexity],
            reason=data.get("reason", ""),
        )
        return _FREEFORM_PRICES[complexity], complexity
    except Exception as e:
        logger.error("Price estimation failed, using default", error=str(e))
        return _FREEFORM_PRICES["medium"], "medium"


async def _job_to_response(job: FreelanceJob, db: AsyncSession) -> FreelanceJobResponse:
    """Convert a FreelanceJob ORM to response schema."""
    template_name = ""
    if job.template_id:
        result = await db.execute(
            select(TaskTemplate.name).where(TaskTemplate.id == job.template_id)
        )
        row = result.scalar_one_or_none()
        if row:
            template_name = row

    return FreelanceJobResponse(
        id=job.id,
        template_id=job.template_id,
        template_name=template_name,
        customer_email=job.customer_email,
        customer_name=job.customer_name,
        description=job.description,
        status=job.status,
        amount_cents=job.amount_cents,
        amount_dollars=_cents_to_dollars(job.amount_cents),
        stripe_payment_link=job.stripe_payment_link,
        stripe_session_id=job.stripe_session_id,
        result_summary=job.result_summary,
        result_files=job.result_files or {},
        created_at=str(job.created_at),
        paid_at=str(job.paid_at) if job.paid_at else None,
        completed_at=str(job.completed_at) if job.completed_at else None,
    )


@router.get("/templates", response_model=TaskTemplateListResponse)
async def list_templates(
    db: AsyncSession = Depends(get_db),
) -> TaskTemplateListResponse:
    """List all available freelance task templates with prices."""
    await _ensure_templates_seeded(db)

    result = await db.execute(
        select(TaskTemplate).where(TaskTemplate.is_active == True).order_by(TaskTemplate.name)
    )
    templates = result.scalars().all()

    return TaskTemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=len(templates),
    )


@router.post("/order", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> OrderCreateResponse:
    """Submit a task order — creates a job and generates a Stripe payment link.

    Accepts either:
    - `template_id` for a pre-defined task template (one-click ordering)
    - `description` for a free-form request (e.g., "test my login page")

    If both are provided, template_id takes precedence.
    Free-form requests use LLM-based price estimation ($5/$10/$25 tiers).
    """
    await _ensure_templates_seeded(db)

    template = None
    is_freeform = False
    job_goal = ""

    # Determine order type
    if body.template_id:
        # Template-based order
        result = await db.execute(
            select(TaskTemplate).where(TaskTemplate.id == body.template_id)
        )
        template = result.scalar_one_or_none()

        if template is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task template not found",
            )

        if not template.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This task template is no longer available",
            )

        amount_cents = template.price_cents
        job_goal = body.description or template.description
        order_name = template.name
    elif body.description:
        # Free-form order — estimate price via LLM
        is_freeform = True
        amount_cents, complexity = await _estimate_price(body.description)
        job_goal = body.description
        order_name = f"Custom: {body.description[:60]}..."
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either template_id or description must be provided",
        )

    # Create the job
    job = FreelanceJob(
        id=uuid.uuid4(),
        template_id=template.id if template else None,
        customer_email=body.customer_email,
        customer_name=body.customer_name,
        description=job_goal,
        status="pending",
        amount_cents=amount_cents,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Try to generate Stripe payment link
    stripe_link = None
    if settings.stripe_secret_key and settings.stripe_secret_key != "sk_test_placeholder":
        try:
            stripe = await _get_stripe_client()
            product_name = order_name
            product = stripe.Product.create(
                name=f"Jarvis Freelance: {product_name}",
                description=f"{job_goal[:100]}...",
            )
            price = stripe.Price.create(
                product=product.id,
                unit_amount=amount_cents,
                currency="usd",
            )
            payment_link = stripe.PaymentLink.create(
                line_items=[{"price": price.id, "quantity": 1}],
                metadata={"job_id": str(job.id)},
            )
            stripe_link = payment_link.url

            job.stripe_payment_link = stripe_link
            await db.commit()
        except Exception as e:
            logger.error("Failed to create Stripe payment link", error=str(e))
            # Job still created — just without a payment link
            pass

    logger.info(
        "Freelance order created",
        job_id=str(job.id),
        is_freeform=is_freeform,
        amount=amount_cents,
    )

    return OrderCreateResponse(
        job_id=job.id,
        template_name=order_name if not is_freeform else None,
        amount_cents=amount_cents,
        amount_dollars=_cents_to_dollars(amount_cents),
        status=job.status,
        stripe_payment_link=stripe_link,
        message="Order created. Complete payment to start processing.",
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Stripe webhook endpoint — marks jobs as paid when payment succeeds.

    Expects a raw JSON body with Stripe event type and data.
    """
    import json as json_module

    body = await request.body()
    try:
        payload = json_module.loads(body)
    except json_module.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    event_type = payload.get("type", "")
    logger.info("Stripe webhook received", event_type=event_type)

    if event_type == "checkout.session.completed":
        session_data = payload.get("data", {}).get("object", {})
        metadata = session_data.get("metadata", {})
        job_id_str = metadata.get("job_id")

        if job_id_str:
            try:
                job_id = uuid.UUID(job_id_str)
                result = await db.execute(
                    select(FreelanceJob).where(FreelanceJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if job and job.status == "pending":
                    job.status = "paid"
                    job.stripe_session_id = session_data.get("id", "")
                    from datetime import datetime, timezone

                    job.paid_at = datetime.now(timezone.utc)
                    await db.commit()
                    logger.info("Job marked as paid", job_id=job_id_str)
            except (ValueError, Exception) as e:
                logger.error("Failed to process webhook", error=str(e))

    return {"status": "ok"}


@router.get("/jobs", response_model=FreelanceJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobListResponse:
    """List all freelance jobs for the current user.

    Requires authentication. Shows job status, payment info, and results.
    """
    await _ensure_templates_seeded(db)

    # Build query — show all jobs (admin view) or filter by customer email matching user
    query = select(FreelanceJob)
    count_query = select(func.count(FreelanceJob.id))

    if status_filter:
        query = query.where(FreelanceJob.status == status_filter)
        count_query = count_query.where(FreelanceJob.status == status_filter)

    # Get total count
    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Get paginated results
    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(FreelanceJob.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    jobs = result.scalars().all()

    items = []
    for job in jobs:
        items.append(await _job_to_response(job, db))

    pages = max(1, (total + page_size - 1) // page_size)

    return FreelanceJobListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/jobs/{job_id}", response_model=FreelanceJobResponse)
async def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FreelanceJobResponse:
    """Get details of a specific freelance job including deliverables."""
    await _ensure_templates_seeded(db)

    result = await db.execute(
        select(FreelanceJob).where(FreelanceJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return await _job_to_response(job, db)