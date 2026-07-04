"""Voice-related Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SynthesizeRequest(BaseModel):
    """TTS synthesis request payload."""

    text: str = Field(..., min_length=1, max_length=5000)


class TranscriptionResponse(BaseModel):
    """STT transcription response."""

    text: str
