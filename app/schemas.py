"""Pydantic schemas used by the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PhishingCaseCreate(BaseModel):
    """A single labeled case to store in the database."""

    text: str = Field(..., min_length=1, description="통화 녹취 또는 문자 내용")
    label: int = Field(..., ge=0, le=1, description="보이스피싱이면 1, 정상이면 0")
    reason: str = Field("", description="라벨링 근거 또는 사례 설명")
    source: str = Field("", description="데이터 출처")


class PhishingCase(PhishingCaseCreate):
    """A stored case returned by the API."""

    id: int
    created_at: str


class ImportResult(BaseModel):
    """Result returned after importing a JSON file."""

    inserted_count: int
    skipped_count: int


class RagDetectRequest(BaseModel):
    """RAG detection request."""

    text: str = Field(..., min_length=1, description="탐지할 문장")
    top_k: int = Field(5, ge=1, le=20, description="검색할 유사 사례 개수")


class RetrievedCase(BaseModel):
    """A similar case retrieved from the database."""

    id: int
    text: str
    label: int
    reason: str
    source: str
    similarity: float


class RagDetectResponse(BaseModel):
    """RAG detection response with generated evidence."""

    is_phishing: bool
    risk_level: str
    risk_score: float
    matched_patterns: list[str]
    evidence: str
    retrieved_cases: list[RetrievedCase]
