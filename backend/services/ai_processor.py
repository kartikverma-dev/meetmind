"""Claude API service for MOM and executive summary generation."""

import json
import logging
import re

from anthropic import AsyncAnthropic

from config import get_settings
from models.schemas import MOM

logger = logging.getLogger(__name__)

MOM_SYSTEM_PROMPT = """You are an expert meeting analyst. Given a meeting transcript, extract structured Minutes of Meeting (MOM) and an executive summary.

Return ONLY valid JSON with this exact structure (no markdown fences):
{
  "mom": {
    "attendees": ["Name 1", "Name 2"],
    "date": "extracted date or null",
    "agenda": ["agenda item 1", "agenda item 2"],
    "decisions": ["decision 1", "decision 2"],
    "action_items": [
      {
        "task": "what needs to be done",
        "owner": "person name",
        "deadline": "date or null"
      }
    ]
  },
  "summary": "Executive summary as exactly 5 bullet points separated by newlines. Each bullet starts with •"
}

Rules:
- Infer attendee names from the transcript when mentioned.
- If information is missing, use empty arrays or null.
- Action items must have task and owner; deadline is optional.
- Summary must be exactly 5 concise bullet points."""


def _parse_claude_response(raw_text: str) -> tuple[MOM, str]:
    """Extract and validate JSON from Claude's response."""
    text = raw_text.strip()

    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        text = fence_match.group(1).strip()

    data = json.loads(text)
    mom = MOM.model_validate(data["mom"])
    summary = data["summary"].strip()
    return mom, summary


async def process_transcript(transcript: str) -> tuple[MOM, str]:
    """
    Send transcript to Claude and return structured MOM + executive summary.

    Args:
        transcript: Full meeting transcript text.

    Returns:
        Tuple of (MOM model, summary string).
    """
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    logger.info("Sending transcript to Claude (%d chars)", len(transcript))

    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=4096,
        system=MOM_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Analyze this meeting transcript:\n\n{transcript}",
            }
        ],
    )

    raw_text = message.content[0].text
    mom, summary = _parse_claude_response(raw_text)

    logger.info(
        "Claude processing complete: %d attendees, %d action items",
        len(mom.attendees),
        len(mom.action_items),
    )
    return mom, summary
