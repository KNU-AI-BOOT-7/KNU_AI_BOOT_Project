"""API에서 사용하는 Pydantic 스키마."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TrainingCaseTurnCreate(BaseModel):
    """학습 사례 안의 단일 발화."""

    turn_index: int = Field(..., ge=1, description="통화 안에서의 발화 순서")
    text: str = Field(..., min_length=1, description="발화 내용")


class TrainingCaseCreate(BaseModel):
    """학습과 RAG 검색에 사용할 단일 사례."""

    external_id: str = Field("", description="원본 데이터의 세션 또는 통화 ID")
    text: str = Field("", description="학습/RAG에 사용할 정제 텍스트. 비어 있으면 turns로 자동 생성")
    label: int = Field(..., ge=0, le=1, description="정상은 0, 보이스피싱은 1")
    source: str = Field("", description="데이터 출처")
    turns: list[TrainingCaseTurnCreate] = Field(default_factory=list, description="통화 내부 발화 목록")


class TrainingCaseTurn(TrainingCaseTurnCreate):
    """DB에 저장된 학습 사례 발화."""

    id: int
    case_id: int
    created_at: str


class TrainingCase(TrainingCaseCreate):
    """DB에 저장된 학습 사례."""

    id: int
    created_at: str
    turns: list[TrainingCaseTurn] = Field(default_factory=list)


class ImportResult(BaseModel):
    """JSON 파일 가져오기 이후 반환하는 결과."""

    inserted_count: int
    skipped_count: int


class CallLogCreate(BaseModel):
    """실시간 통화 분석을 시작할 때 생성하는 통화 로그."""

    device_id: Optional[int] = Field(None, description="기기 ID")
    name: str = Field("", description="통화기록 이름")
    file_type: str = Field("realtime", description="realtime 또는 recording")


class CallLog(BaseModel):
    """탐지 결과가 누적되는 통화 기록."""

    id: int
    device_id: Optional[int]
    name: str
    file_type: str
    status: str
    risk_score: float
    risk_level: str
    detected_label: int
    phishing_type: str
    core_evidence: str
    created_at: str
    updated_at: str


class RiskLevelCounts(BaseModel):
    """통화 기록 목록에서 리스크 레벨별 개수를 표현한다."""

    low: int = 0
    medium: int = 0
    high: int = 0


class CallLogListItem(BaseModel):
    """통화 기록 목록 화면에 필요한 단일 항목."""

    id: int
    called_at: str
    risk_score: float
    risk_level: str
    phishing_type: str
    file_type: str


class CallLogListResponse(BaseModel):
    """통화 기록 목록 조회 응답."""

    risk_level_counts: RiskLevelCounts
    calls: list[CallLogListItem]


class CallLogDetail(BaseModel):
    """통화 기록 상세 화면에 필요한 탐지 정보."""

    id: int
    phishing_type: str
    matched_patterns: list[str]
    core_evidence: str


class CallMessageCreate(BaseModel):
    """통화 중 클라이언트가 분석 요청으로 보내는 발화."""

    content: str = Field(..., min_length=1, description="발화 내용")
    turn_index: Optional[int] = Field(None, ge=1, description="대화 순서")


class CallMessage(BaseModel):
    """DB에 저장된 통화 발화."""

    id: int
    log_id: int
    turn_index: int
    content: str
    created_at: str


class NotificationCreate(BaseModel):
    """위험 탐지 시 클라이언트 또는 사용자에게 보낸 알림 기록."""

    reason: str = Field(..., min_length=1, description="알림을 보낸 근거")
    message: str = Field(..., min_length=1, description="알림 메시지")
    status: str = Field("sent", description="sent, failed 등 발송 상태")


class NotificationLog(NotificationCreate):
    """DB에 저장된 알림 이력."""

    id: int
    log_id: int
    created_at: str


class RagDetectRequest(BaseModel):
    """RAG 탐지 요청."""

    text: str = Field(..., min_length=1, description="탐지할 문장 또는 누적 통화 내용")
    top_k: int = Field(5, ge=1, le=20, description="검색할 유사 사례 개수")


class RetrievedCase(BaseModel):
    """DB에서 검색된 유사 학습 사례."""

    id: int
    external_id: str
    text: str
    label: int
    source: str
    similarity: float


class RagDetectResponse(BaseModel):
    """생성된 핵심근거를 포함한 RAG 탐지 응답."""

    is_phishing: bool
    risk_level: str
    risk_score: float
    matched_patterns: list[str]
    core_evidence: str
    retrieved_cases: list[RetrievedCase]


class DetectionResult(BaseModel):
    """DB에 저장된 단일 탐지 결과."""

    id: int
    log_id: int
    risk_score: float
    risk_level: str
    detected_label: int
    core_evidence: str
    matched_patterns: list[str]
    retrieved_case_ids: list[int]
    model_version: str
    created_at: str


class RealtimeAnalysisStartRequest(CallLogCreate):
    """실시간 분석 시작 메시지."""

    type: str = Field("start", description="메시지 타입")


class RealtimeAnalysisMessageRequest(CallMessageCreate):
    """실시간 분석 발화 메시지."""

    type: str = Field("message", description="메시지 타입")
