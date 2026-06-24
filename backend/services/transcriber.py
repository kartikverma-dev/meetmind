"""Local Whisper transcription service."""

import asyncio
import logging
from functools import lru_cache

import whisper

from config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _load_model(model_name: str):
    """Load and cache the Whisper model (blocking, called once)."""
    logger.info("Loading Whisper model: %s", model_name)
    return whisper.load_model(model_name)


def _transcribe_sync(file_path: str, model_name: str) -> str:
    """Run Whisper transcription synchronously in a worker thread."""
    model = _load_model(model_name)
    result = model.transcribe(file_path, fp16=False)
    return result["text"].strip()


async def transcribe_audio(file_path: str) -> str:
    """
    Transcribe an audio/video file using local OpenAI Whisper.

    Args:
        file_path: Absolute or relative path to the audio file.

    Returns:
        Transcript text.
    """
    settings = get_settings()
    model_name = settings.whisper_model or "base"
    logger.info("Transcribing file: %s (model=%s)", file_path, model_name)

    transcript = await asyncio.to_thread(
        _transcribe_sync, file_path, model_name
    )
    logger.info("Transcription complete (%d chars)", len(transcript))
    return transcript
