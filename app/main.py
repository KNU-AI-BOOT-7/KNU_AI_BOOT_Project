"""FastAPI entrypoint for the voice phishing RAG detection API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.database import init_db
from app.repository import get_case, insert_case, insert_cases, list_cases, parse_cases_json
from app.schemas import (
    ImportResult,
    PhishingCase,
    PhishingCaseCreate,
    RagDetectRequest,
    RagDetectResponse,
)
from app.services.rag_detector import RagPhishingDetector


detector = RagPhishingDetector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the SQLite DB when the API server starts."""
    init_db()
    yield


app = FastAPI(
    title="Voice Phishing RAG Detection API",
    description="JSON 사례를 DB에 저장하고 RAG 기반으로 보이스피싱 위험도와 근거를 생성합니다.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/cases", response_model=PhishingCase)
def create_case(case: PhishingCaseCreate) -> PhishingCase:
    """Store one voice phishing or normal case in the database."""
    case_id = insert_case(case)
    return get_case(case_id)


@app.post("/cases/import-json", response_model=ImportResult)
async def import_cases_json(file: UploadFile = File(...)) -> ImportResult:
    """
    Upload a JSON file and save valid voice phishing cases to SQLite.

    JSON can be either a list of cases or an object with a `cases` list.
    """
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="JSON 파일만 업로드할 수 있습니다.")

    try:
        raw_bytes = await file.read()
        cases, skipped_count = parse_cases_json(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON 파일을 읽을 수 없습니다.") from exc

    inserted_count = insert_cases(cases)
    return ImportResult(inserted_count=inserted_count, skipped_count=skipped_count)


@app.get("/cases", response_model=list[PhishingCase])
def get_cases(limit: int = 100) -> list[PhishingCase]:
    """Return recently inserted cases."""
    return list_cases(limit=limit)


@app.post("/detect/rag", response_model=RagDetectResponse)
def detect_rag(request: RagDetectRequest) -> RagDetectResponse:
    """Detect voice phishing risk using DB-backed RAG and generated evidence."""
    try:
        return detector.detect(text=request.text, top_k=request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
