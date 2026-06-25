"""Structured JSON Logger with sensitive information redaction."""

import json
import logging
import re
from datetime import datetime
import contextvars

# Context variables to track request ID and user ID dynamically in async context
request_id_var = contextvars.ContextVar("request_id", default="-")
user_id_var = contextvars.ContextVar("user_id", default="-")

SENSITIVE_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"rzp_(test|live)_[0-9a-zA-Z]{14}"), "[REDACTED_RAZORPAY_KEY]"),
    (re.compile(r"sk-[0-9a-zA-Z]{48}"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"eyJh[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*"), "[REDACTED_JWT]"),
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "[REDACTED_EMAIL]"),
    (re.compile(r'(?i)"password"\s*:\s*"[^"]+"'), '"password": "[REDACTED]"'),
    (re.compile(r'(?i)password=[^&\s]+'), 'password=[REDACTED]'),
]

def redact_message(message: str) -> str:
    """Scan and redact sensitive data like keys, emails, JWTs and passwords from logs."""
    if not isinstance(message, str):
        message = str(message)
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message

class JSONFormatter(logging.Formatter):
    """Formats log records into a structured JSON dictionary."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "user_id": user_id_var.get(),
            "message": redact_message(record.getMessage()),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

def setup_logger():
    """Setup and configure the root logger to use JSON formatting and StreamHandler."""
    root_logger = logging.getLogger()
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
