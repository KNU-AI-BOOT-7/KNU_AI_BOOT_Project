"""VoiceGuard AI FastAPI 애플리케이션 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

from app.api.routes import router as rest_router
from app.api.websocket import router as websocket_router
from app.database import init_db
from app.services.call_analyzer import preload_koelectra_model


if load_dotenv:
    load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """API 서버 시작 시 DB와 모델 리소스를 준비한다."""
    init_db()
    await preload_koelectra_model()
    yield


app = FastAPI(
    title="Voice Phishing RAG Detection API",
    description="실시간 통화 음성을 분석해 보이스피싱 위험도와 핵심근거를 생성",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(rest_router)
app.include_router(websocket_router)
