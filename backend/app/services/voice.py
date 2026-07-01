"""Voice service — STT, TTS, and VAD for the Jarvis assistant."""

from __future__ import annotations

import io
import struct
from collections.abc import AsyncGenerator
from typing import Any

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class VoiceService:
    """Speech-to-Text, Text-to-Speech, and Voice Activity Detection."""

    def __init__(self) -> None:
        self._openai_client: Any = None
        self._silero_model: Any = None
        self._vad: Any = None

    # ------------------------------------------------------------------ #
    #  Speech-to-Text (OpenAI Whisper API)
    # ------------------------------------------------------------------ #

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe audio bytes to text using OpenAI Whisper API.

        Accepts raw PCM audio (16kHz, mono, 16-bit) or WAV format.
        Returns transcribed text, or empty string on failure.
        """
        if not audio_bytes:
            logger.warning("Empty audio bytes received for transcription")
            return ""

        try:
            # Ensure audio is in WAV format for Whisper API
            wav_bytes = self._ensure_wav(audio_bytes)

            import openai

            client = self._get_openai_client()
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.wav", io.BytesIO(wav_bytes), "audio/wav"),
                response_format="text",
            )
            result = transcript.strip() if isinstance(transcript, str) else str(transcript).strip()
            logger.info("Transcription completed", length=len(result))
            return result

        except Exception as e:
            logger.error("Transcription failed", error=str(e))
            return ""

    def _get_openai_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._openai_client is None:
            import openai

            self._openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        return self._openai_client

    def _ensure_wav(self, audio_bytes: bytes) -> bytes:
        """Ensure audio is in WAV format. If it starts with RIFF header, assume WAV."""
        if audio_bytes[:4] == b"RIFF":
            return audio_bytes

        # Wrap raw PCM data in a WAV container
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)  # 16kHz
            wf.writeframes(audio_bytes)
        return buf.getvalue()

    # ------------------------------------------------------------------ #
    #  Text-to-Speech (Edge-TTS)
    # ------------------------------------------------------------------ #

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to speech using Edge-TTS.

        Streams MP3 audio chunks as they're generated using a British voice.
        Yields raw bytes chunks.
        """
        if not text.strip():
            logger.warning("Empty text received for synthesis")
            return

        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, voice="en-GB-RyanNeural")
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    yield chunk["data"]
        except Exception as e:
            logger.error("Synthesis failed", error=str(e))
            raise

    # ------------------------------------------------------------------ #
    #  Voice Activity Detection (Silero VAD + WebRTC VAD fallback)
    # ------------------------------------------------------------------ #

    def detect_speech(self, audio_chunk: bytes) -> bool:
        """Detect if speech is present in an audio chunk.

        Uses Silero VAD (ONNX) as primary, falls back to WebRTC VAD.
        Accepts 16-bit PCM mono audio at 16kHz (or 8kHz for WebRTC fallback).
        Returns True if speech is detected, False otherwise.
        """
        if not audio_chunk or len(audio_chunk) < 320:  # minimum 20ms at 16kHz
            return False

        try:
            return self._detect_speech_silero(audio_chunk)
        except Exception as e:
            logger.debug("Silero VAD failed, falling back to WebRTC", error=str(e))
            return self._detect_speech_webrtc(audio_chunk)

    def _detect_speech_silero(self, audio_chunk: bytes) -> bool:
        """Detect speech using Silero VAD."""
        if self._silero_model is None:
            import silero_vad

            self._silero_model = silero_vad.load_silero_vad()
            self._silero_model.reset_states()

        # Convert PCM bytes to float32 numpy array
        import numpy as np

        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float32 = audio_int16.astype(np.float32) / 32768.0

        # Get speech probability
        speech_prob = self._silero_model.process_chunk(audio_float32)
        return speech_prob > 0.5

    def _detect_speech_webrtc(self, audio_chunk: bytes) -> bool:
        """Detect speech using WebRTC VAD (fallback)."""
        if self._vad is None:
            import webrtcvad

            self._vad = webrtcvad.Vad(2)  # Aggressiveness: 2 (medium)

        # WebRTC VAD requires 16-bit PCM, 16kHz (or 8kHz/32kHz/48kHz)
        # Ensure we have enough data for 30ms frame (480 samples at 16kHz)
        if len(audio_chunk) < 480:
            # Pad with silence
            audio_chunk = audio_chunk + b"\x00" * (480 - len(audio_chunk))

        try:
            return self._vad.is_speech(audio_chunk, 16000)
        except Exception:
            return False

    def reset_vad(self) -> None:
        """Reset VAD internal state (call between speech segments)."""
        if self._silero_model is not None:
            try:
                self._silero_model.reset_states()
            except Exception:
                pass


# Singleton
_voice_service: VoiceService | None = None


def get_voice_service() -> VoiceService:
    """Get or create the VoiceService singleton."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceService()
    return _voice_service