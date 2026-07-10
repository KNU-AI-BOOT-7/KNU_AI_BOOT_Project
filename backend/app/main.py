"""VoiceGuard AI FastAPI 애플리케이션 진입점."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

from backend.app.api.routes import router as rest_router
from backend.app.api.websocket import router as websocket_router
from backend.app.database import init_db
from backend.app.paths import ENV_PATH
from backend.app.services.call_analyzer import preload_koelectra_model


if load_dotenv:
    load_dotenv(ENV_PATH)


DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://localhost:8081",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:8081",
]


def _get_cors_origins() -> list[str]:
    """CORS를 허용할 프론트엔드 origin 목록을 기본값과 환경변수에서 읽는다."""
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    env_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    return list(dict.fromkeys(DEFAULT_CORS_ORIGINS + env_origins))


def _get_cors_allow_credentials(cors_origins: list[str]) -> bool:
    """와일드카드 Origin을 쓰는 경우에는 브라우저 규칙상 credentials를 끈다."""
    return "*" not in cors_origins


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
cors_origins = _get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=_get_cors_allow_credentials(cors_origins),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(rest_router)
app.include_router(websocket_router)
