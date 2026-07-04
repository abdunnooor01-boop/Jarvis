"""Vision API routes — screenshot analysis and screen understanding."""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.vision import (
    AnalyzeRequest,
    AnalyzeResponse,
    CompareRequest,
    CompareResponse,
    DescribeResponse,
    ExtractTextResponse,
    FindElementRequest,
    FindElementResponse,
    TextRegion,
)
from app.services.vision import get_vision_service

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])


def _decode_image(image_b64: str) -> bytes:
    """Decode a base64 image string to bytes."""
    try:
        # Strip data URL prefix if present
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        return base64.b64decode(image_b64)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid base64 image data: {e!s}",
        )


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_screenshot(
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> AnalyzeResponse:
    """Analyze a screenshot with an optional prompt.

    Accepts base64-encoded image data and returns a natural language description.
    """
    image_bytes = _decode_image(body.image)

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image data",
        )

    vision_service = get_vision_service()
    result = await vision_service.analyze_screenshot(image_bytes, body.prompt)

    return AnalyzeResponse(
        description=result["description"],
        model=result["model"],
        processing_time_ms=result["processing_time_ms"],
    )


@router.post("/find", response_model=FindElementResponse)
async def find_element(
    body: FindElementRequest,
    current_user: User = Depends(get_current_user),
) -> FindElementResponse:
    """Find a UI element on screen by description.

    Returns coordinates and confidence for the matching element.
    """
    image_bytes = _decode_image(body.image)

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image data",
        )

    if not body.description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Element description cannot be empty",
        )

    vision_service = get_vision_service()
    result = await vision_service.find_element(image_bytes, body.description)

    return FindElementResponse(
        found=result["found"],
        x=result.get("x"),
        y=result.get("y"),
        width=result.get("width"),
        height=result.get("height"),
        confidence=result["confidence"],
        label=result.get("label", ""),
        explanation=result.get("explanation", ""),
    )


@router.post("/describe", response_model=DescribeResponse)
async def describe_screen(
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> DescribeResponse:
    """Get a detailed description of everything visible on screen."""
    image_bytes = _decode_image(body.image)

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image data",
        )

    vision_service = get_vision_service()
    result = await vision_service.describe_screen(image_bytes)

    return DescribeResponse(
        description=result["description"],
        model=result["model"],
        processing_time_ms=result["processing_time_ms"],
    )


@router.post("/compare", response_model=CompareResponse)
async def compare_screenshots(
    body: CompareRequest,
    current_user: User = Depends(get_current_user),
) -> CompareResponse:
    """Compare two screenshots and describe what changed."""
    before_bytes = _decode_image(body.image_a)
    after_bytes = _decode_image(body.image_b)

    if not before_bytes or not after_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both images are required and must not be empty",
        )

    vision_service = get_vision_service()
    result = await vision_service.compare_screenshots(before_bytes, after_bytes)

    return CompareResponse(
        changes_detected=result["changes_detected"],
        description=result["description"],
        model=result["model"],
        processing_time_ms=result["processing_time_ms"],
    )


@router.post("/extract-text", response_model=ExtractTextResponse)
async def extract_text(
    body: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
) -> ExtractTextResponse:
    """Extract text regions from a screenshot with coordinates."""
    image_bytes = _decode_image(body.image)

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image data",
        )

    vision_service = get_vision_service()
    result = await vision_service.extract_text_regions(image_bytes)

    return ExtractTextResponse(
        regions=[TextRegion(**r) for r in result.get("regions", [])],
        full_text=result.get("full_text", ""),
        model=result["model"],
        processing_time_ms=result["processing_time_ms"],
    )