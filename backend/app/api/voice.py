"""Voice API routes — STT and TTS endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.voice import get_voice_service
from app.schemas.voice import SynthesizeRequest, TranscriptionResponse

router = APIRouter(prefix="/api/v1/voice", tags=["voice"])


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> TranscriptionResponse:
    """Transcribe an audio file to text using Whisper API.

    Accepts multipart form upload with an audio file (WAV, MP3, etc.).
    Returns JSON with the transcribed text.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided",
        )

    # Validate content type
    allowed_types = [
        "audio/wav", "audio/wave", "audio/x-wav",
        "audio/mpeg", "audio/mp3",
        "audio/ogg", "audio/webm",
        "audio/flac",
    ]
    content_type = file.content_type or ""
    if content_type and content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format: {content_type}. "
                   f"Supported: {', '.join(allowed_types)}",
        )

    # Read audio data
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty audio file",
        )

    voice_service = get_voice_service()
    text = await voice_service.transcribe(audio_bytes)

    return TranscriptionResponse(text=text)


@router.post("/synthesize")
async def synthesize_speech(
    body: SynthesizeRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Synthesize text to speech using Edge-TTS.

    Accepts JSON with text. Returns streaming MP3 audio.
    """
    if not body.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text cannot be empty",
        )

    if len(body.text) > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text too long (max 5000 characters)",
        )

    voice_service = get_voice_service()

    async def audio_stream() -> AsyncGenerator[bytes, None]:
        """Stream audio chunks from TTS."""
        async for chunk in voice_service.synthesize(body.text):
            yield chunk

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="speech.mp3"',
            "X-Accel-Buffering": "no",
        },
    )


# Type alias for the async generator used in StreamingResponse
from collections.abc import AsyncGenerator  # noqa: F811, E402