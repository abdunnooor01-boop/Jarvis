"""Tests for the voice service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.voice import VoiceService


class TestVoiceServiceTranscribe:
    """Tests for VoiceService.transcribe."""

    @pytest.mark.asyncio
    async def test_transcribe_empty_audio(self) -> None:
        """Test that empty audio returns empty string."""
        service = VoiceService()
        result = await service.transcribe(b"")
        assert result == ""

    @pytest.mark.asyncio
    async def test_transcribe_success(self) -> None:
        """Test successful transcription via Whisper API."""
        service = VoiceService()

        mock_client = MagicMock()
        mock_transcribe = AsyncMock(return_value="Hello world")
        mock_client.audio.transcriptions.create = mock_transcribe

        with patch.object(service, "_get_openai_client", return_value=mock_client):
            result = await service.transcribe(b"fake_audio_data")

        assert result == "Hello world"
        mock_transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_transcribe_api_error(self) -> None:
        """Test that API errors return empty string."""
        service = VoiceService()

        mock_client = MagicMock()
        mock_client.audio.transcriptions.create = AsyncMock(
            side_effect=Exception("API error")
        )

        with patch.object(service, "_get_openai_client", return_value=mock_client):
            result = await service.transcribe(b"fake_audio_data")

        assert result == ""


class TestVoiceServiceSynthesize:
    """Tests for VoiceService.synthesize."""

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self) -> None:
        """Test that empty text yields nothing."""
        service = VoiceService()
        chunks = []
        async for chunk in service.synthesize(""):
            chunks.append(chunk)
        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_synthesize_whitespace_only(self) -> None:
        """Test that whitespace-only text yields nothing."""
        service = VoiceService()
        chunks = []
        async for chunk in service.synthesize("   "):
            chunks.append(chunk)
        assert len(chunks) == 0

    @pytest.mark.asyncio
    async def test_synthesize_success(self) -> None:
        """Test successful TTS synthesis."""
        service = VoiceService()

        async def mock_stream():
            yield {"type": "audio", "data": b"mp3_chunk_1"}
            yield {"type": "audio", "data": b"mp3_chunk_2"}
            yield {"type": "WordBoundary", "data": None}  # Should be skipped

        mock_communicate = MagicMock()
        mock_communicate.stream = mock_stream

        with patch("edge_tts.Communicate", return_value=mock_communicate):
            chunks = []
            async for chunk in service.synthesize("Hello"):
                chunks.append(chunk)

        assert chunks == [b"mp3_chunk_1", b"mp3_chunk_2"]

    @pytest.mark.asyncio
    async def test_synthesize_error(self) -> None:
        """Test that synthesis errors propagate."""
        service = VoiceService()

        with patch("edge_tts.Communicate", side_effect=Exception("TTS error")):
            with pytest.raises(Exception, match="TTS error"):
                async for _ in service.synthesize("Hello"):
                    pass  # noqa: WPS420


class TestVoiceServiceVAD:
    """Tests for VoiceService VAD methods."""

    def test_detect_speech_empty_chunk(self) -> None:
        """Test that empty chunk returns False."""
        service = VoiceService()
        assert service.detect_speech(b"") is False

    def test_detect_speech_small_chunk(self) -> None:
        """Test that very small chunk returns False."""
        service = VoiceService()
        assert service.detect_speech(b"\x00" * 100) is False

    def test_detect_speech_silero_import_error(self) -> None:
        """Test fallback to WebRTC when Silero fails."""
        service = VoiceService()
        chunk = b"\x00" * 640  # 20ms of silence at 16kHz mono 16-bit

        with patch.object(service, "_detect_speech_silero", side_effect=ImportError("No silero")):
            with patch.object(service, "_detect_speech_webrtc", return_value=False):
                result = service.detect_speech(chunk)
                assert result is False

    def test_reset_vad(self) -> None:
        """Test that reset_vad does not raise."""
        service = VoiceService()
        service.reset_vad()  # Should not raise even without model loaded