"""Input sanitization helper module for SQL injection, XSS, and path traversal protection."""

import re
import html
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

# Pattern to detect common SQL injection signatures
SQL_KEYWORDS_PATTERN = re.compile(
    r"\b(select|insert|update|delete|drop|union|alter|where|truncate|or\s+1\s*=\s*1|--)\b", 
    re.IGNORECASE
)

# Pattern to detect scripting / XSS vectors
SCRIPT_TAGS_PATTERN = re.compile(
    r"(<script|javascript:|onerror|onload|alert\()", 
    re.IGNORECASE
)

def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Sanitize user-provided text inputs to prevent XSS, remove control characters, and limit length."""
    if not text:
        return ""
    # Strip null bytes and control characters
    text = "".join(ch for ch in text if ord(ch) >= 32 or ch in "\n\r\t")
    text = text.strip()
    text = text[:max_length]  # Enforce length limit
    text = html.escape(text)  # Escape HTML entities
    return text

def sanitize_filename(filename: str) -> str:
    """Sanitize uploaded file names to prevent directory traversal and invalid characters."""
    if not filename:
        return "unnamed_file"
    # Only allow alphanumeric, dash, underscore, dot
    filename = re.sub(r"[^\w\-_\.]", "_", filename)
    filename = filename[:100]  # Max 100 chars
    return filename

def sanitize_uuid(uuid_str: str) -> str:
    """Validate UUID format. Returns string if valid, raises ValueError if not."""
    if not uuid_str:
        raise ValueError("UUID string is empty")
    try:
        val = UUID(uuid_str)
        return str(val)
    except ValueError as e:
        raise ValueError(f"Invalid UUID: {uuid_str}") from e

def detect_injection_attempt(text: str) -> bool:
    """Returns True if SQL keywords or script tags are found in the text input."""
    if not text:
        return False
    if SQL_KEYWORDS_PATTERN.search(text) or SCRIPT_TAGS_PATTERN.search(text):
        logger.warning("Injection attempt detected: %s", text[:200])
        return True
    return False
