"""MeetMind API — Phase 1: Backend Core."""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes.meetings import router as meetings_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MeetMind API starting up")
    yield
    logger.info("MeetMind API shutting down")


app = FastAPI(
    title="MeetMind API",
    description="AI-powered meeting summarizer",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow local frontend during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meetings_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "meetmind-api"}
