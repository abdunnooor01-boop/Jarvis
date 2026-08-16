"""Pydantic schemas for vision/image analysis."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request to analyze a screenshot."""

    image: str = Field(..., description="Base64-encoded image data (PNG/JPEG)")
    prompt: str = Field(
        default="Describe what's on this screen in detail",
        description="Optional prompt to guide the analysis",
    )


class TextRegion(BaseModel):
    """A text region identified on screen."""

    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


class AnalyzeResponse(BaseModel):
    """Response from screenshot analysis."""

    description: str
    model: str = "gpt-4o"
    processing_time_ms: float = 0.0


class FindElementRequest(BaseModel):
    """Request to find an element on screen."""

    image: str = Field(..., description="Base64-encoded image data")
    description: str = Field(
        ...,
        description="Description of the element to find, e.g. 'the login button'",
    )


class FindElementResponse(BaseModel):
    """Response from element search."""

    found: bool
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    confidence: float = 0.0
    label: str = ""
    explanation: str = ""


class DescribeResponse(BaseModel):
    """Response from screen description."""

    description: str
    model: str = "gpt-4o"
    processing_time_ms: float = 0.0


class CompareRequest(BaseModel):
    """Request to compare two screenshots."""

    image_a: str = Field(..., description="Base64-encoded before image")
    image_b: str = Field(..., description="Base64-encoded after image")


class CompareResponse(BaseModel):
    """Response from screenshot comparison."""

    changes_detected: bool
    description: str
    model: str = "gpt-4o"
    processing_time_ms: float = 0.0


class ExtractTextResponse(BaseModel):
    """Response from text region extraction."""

    regions: list[TextRegion]
    full_text: str
    model: str = "gpt-4o"
    processing_time_ms: float = 0.0