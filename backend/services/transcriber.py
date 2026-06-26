"""Local Whisper transcription service with language selection support."""

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


def _transcribe_sync(file_path: str, model_name: str, language: str = "auto") -> str:
    """Run Whisper transcription synchronously in a worker thread."""
    model = _load_model(model_name)
    
    kwargs = {"fp16": False}
    if language and language != "auto":
        kwargs["language"] = language
        logger.info("Whisper transcribing with explicit language: %s", language)
    else:
        logger.info("Whisper transcribing with auto-detected language")
        
    result = model.transcribe(file_path, **kwargs)
    return result["text"].strip()


async def transcribe_audio(file_path: str, language: str = "auto") -> str:
    """
    Transcribe an audio/video file using local OpenAI Whisper.

    Args:
        file_path: Absolute or relative path to the audio file.
        language: Optional language code (e.g. 'hi', 'en', 'es') or 'auto'

    Returns:
        Transcript text.
    """
    settings = get_settings()
    model_name = settings.whisper_model or "base"
    logger.info("Transcribing file: %s (model=%s, lang=%s)", file_path, model_name, language)

    transcript = await asyncio.to_thread(
        _transcribe_sync, file_path, model_name, language
    )
    logger.info("Transcription complete (%d chars)", len(transcript))
    return transcript
