"""Centralized rate limiting configuration and limits."""

from slowapi import Limiter
from slowapi.util import get_remote_address

# Configure global Limiter instance using remote client IP
limiter = Limiter(key_func=get_remote_address)

# Centralized rate limit configurations
LIMIT_LOGIN = "5/minute"
LIMIT_SIGNUP = "3/minute"
LIMIT_UPLOAD = "10/minute"
LIMIT_QA = "20/minute"
LIMIT_CRON = "1/minute"
