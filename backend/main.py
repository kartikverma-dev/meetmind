"""MeetMind API main application configuration."""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from config import get_settings
from routes.meetings import router as meetings_router
from routes.auth import router as auth_router
from routes.qa import router as qa_router
from routes.action_items import router as action_items_router
from routes.share import router as share_router
from routes.cron import router as cron_router
from routes.stats import router as stats_router
from utils.limiter import limiter
from utils.logger import setup_logger
from utils.error_handler import global_exception_handler
from middleware.security import (
    SecurityHeadersMiddleware,
    RequestSizeMiddleware,
    HTTPSRedirectMiddleware,
    RequestLoggingMiddleware,
    SuspiciousActivityMiddleware,
    CSRFMiddleware,
)

load_dotenv()

# Initialize structured JSON logger
setup_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "="*50)
    print("      MEETMIND BACKEND STARTED (BETA FREE MODE)")
    print("="*50 + "\n")
    yield

app = FastAPI(
    title="MeetMind API",
    description="AI-powered meeting summarizer",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure slowapi limiter state and error handlers
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure global exception handler for safe client responses and DB logging
app.add_exception_handler(Exception, global_exception_handler)

settings = get_settings()

# Add middlewares in proper execution order - CORS must be the first middleware registered
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://meetmind-nine.vercel.app",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
    expose_headers=["Content-Disposition"],
    max_age=3600,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware)
app.add_middleware(SuspiciousActivityMiddleware)
app.add_middleware(RequestSizeMiddleware)
app.add_middleware(HTTPSRedirectMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Include routes prefixed with /api/v1/ for API versioning
app.include_router(auth_router, prefix="/api/v1")
app.include_router(meetings_router, prefix="/api/v1")
app.include_router(qa_router, prefix="/api/v1")
app.include_router(action_items_router, prefix="/api/v1")
app.include_router(share_router, prefix="/api/v1")
app.include_router(cron_router, prefix="/api/v1")
app.include_router(stats_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {
        "status": "MeetMind backend is live",
        "mode": "Beta Free Mode",
        "documentation": "/docs"
    }

@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    return {"status": "ok"}
