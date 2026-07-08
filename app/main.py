"""보이스피싱 RAG 탐지 API의 FastAPI 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

from app.database import init_db
from app.repository import (
    build_call_text,
    create_call_log,
    get_training_case,
    insert_call_message,
    insert_notification,
    insert_training_case,
    insert_training_cases,
    list_call_logs,
    list_training_cases,
    parse_training_cases_json,
    save_detection_result,
)
from app.schemas import (
    CallLog,
    CallLogCreate,
    CallMessageCreate,
    ImportResult,
    NotificationCreate,
    TrainingCase,
    TrainingCaseCreate,
)
from app.services.rag_detector import RagPhishingDetector


detector = RagPhishingDetector()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """API 서버가 시작될 때 SQLite DB를 초기화"""
    init_db()
    yield


app = FastAPI(
    title="Voice Phishing RAG Detection API",
    description="학습 사례를 DB에 저장하고 RAG 기반으로 보이스피싱 위험도와 핵심근거를 생성",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    """서버 상태 확인 엔드포인트."""
    return {"status": "ok"}


@app.get("/calls", response_model=list[CallLog])
def get_calls(limit: int = 100) -> list[CallLog]:
    """최근 통화 로그를 반환한다."""
    return list_call_logs(limit=limit)


@app.post("/training-cases", response_model=TrainingCase)
def create_training_case(case: TrainingCaseCreate) -> TrainingCase:
    """정상 또는 보이스피싱 학습 사례 1건을 DB에 저장"""
    case_id = insert_training_case(case)
    return get_training_case(case_id)


@app.post("/training-cases/import-json", response_model=ImportResult)
async def import_training_cases_json(file: UploadFile = File(...)) -> ImportResult:
    """
    JSON 파일을 업로드하고 유효한 학습 사례를 SQLite에 저장한다.

    JSON은 사례 리스트이거나 `cases` 리스트를 가진 객체일 수 있다.
    """
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="JSON 파일만 업로드할 수 있습니다.")

    try:
        raw_bytes = await file.read()
        cases, skipped_count = parse_training_cases_json(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="JSON 파일을 읽을 수 없습니다.") from exc

    inserted_count = insert_training_cases(cases)
    return ImportResult(inserted_count=inserted_count, skipped_count=skipped_count)


@app.get("/training-cases", response_model=list[TrainingCase])
def get_training_cases(limit: int = 100) -> list[TrainingCase]:
    """최근 저장된 학습 사례를 반환한다."""
    return list_training_cases(limit=limit)


@app.websocket("/ws/calls/analyze")
async def analyze_call_messages(websocket: WebSocket) -> None:
    """
    클라이언트가 3~4초 단위로 보내는 통화 발화를 받아 실시간 분석을 수행한다.

    백엔드는 통화 발화를 생성하거나 스트리밍하지 않는다. 클라이언트가 보낸
    발화를 저장하고, 누적 통화 내용을 분석한 뒤 피싱 위험이 감지되면
    위험도와 핵심근거를 클라이언트로 반환한다.

    클라이언트 메시지 예시:
    {"type": "start", "device_id": 1, "name": "010-1234-5678"}
    {"type": "message", "role": "caller", "content": "검찰입니다...", "turn_index": 1}
    """
    await websocket.accept()
    log_id: Optional[int] = None

    try:
        while True:
            payload = await websocket.receive_json()
            event_type = payload.get("type", "message")

            if event_type == "start":
                call = create_call_log(
                    CallLogCreate(
                        device_id=payload.get("device_id"),
                        name=str(payload.get("name", "실시간 통화")),
                    )
                )
                log_id = call.id
                await websocket.send_json({"type": "call_started", "call": call.model_dump()})
                continue

            if event_type != "message":
                await websocket.send_json({"type": "error", "message": "지원하지 않는 메시지 타입입니다."})
                continue

            if log_id is None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "통화 발화를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다.",
                    }
                )
                continue

            saved_message = insert_call_message(
                log_id=log_id,
                message=CallMessageCreate(
                    role=str(payload.get("role", "unknown")),
                    content=str(payload.get("content", "")),
                    turn_index=payload.get("turn_index"),
                ),
            )
            detection = _detect_and_persist(log_id=log_id, top_k=int(payload.get("top_k", 5)))
            response = _build_client_analysis_response(log_id, saved_message.model_dump(), detection)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()


def _detect_and_persist(log_id: int, top_k: int = 5) -> dict:
    """누적 통화 내용을 탐지하고 결과와 필요 알림 이력을 DB에 저장한다."""
    call_text = build_call_text(log_id)
    detection = detector.detect(text=call_text, top_k=top_k)
    detected_label = 1 if detection.is_phishing else 0
    retrieved_case_ids = [case.id for case in detection.retrieved_cases]

    saved_result = save_detection_result(
        log_id=log_id,
        risk_score=detection.risk_score,
        risk_level=detection.risk_level,
        detected_label=detected_label,
        core_evidence=detection.core_evidence,
        matched_patterns=detection.matched_patterns,
        retrieved_case_ids=retrieved_case_ids,
    )

    notification = None
    if detection.is_phishing and detection.risk_level == "high":
        notification = insert_notification(
            log_id=log_id,
            notification=NotificationCreate(
                reason=detection.core_evidence,
                message="보이스피싱 위험이 높게 탐지되었습니다. 통화를 종료하고 공식 대표번호로 확인하세요.",
                status="sent",
            ),
        )

    return {
        "is_phishing": detection.is_phishing,
        "risk_level": detection.risk_level,
        "risk_score": detection.risk_score,
        "matched_patterns": detection.matched_patterns,
        "core_evidence": detection.core_evidence,
        "retrieved_cases": [case.model_dump() for case in detection.retrieved_cases],
        "saved_result": saved_result.model_dump(),
        "notification": notification.model_dump() if notification else None,
    }


def _build_client_analysis_response(log_id: int, message: dict, detection: dict) -> dict:
    """
    클라이언트에 반환할 실시간 분석 응답을 만든다.

    정상으로 분석된 경우에는 ACK 수준의 결과만 보내고, 보이스피싱으로
    판단된 경우에는 위험도와 핵심근거를 포함한 상세 결과를 보낸다.
    """
    if not detection["is_phishing"]:
        return {
            "type": "analysis_ack",
            "log_id": log_id,
            "message": message,
            "is_phishing": False,
            "risk_score": detection["risk_score"],
            "risk_level": detection["risk_level"],
        }

    return {
        "type": "phishing_detected",
        "log_id": log_id,
        "message": message,
        "is_phishing": True,
        "risk_score": detection["risk_score"],
        "risk_level": detection["risk_level"],
        "matched_patterns": detection["matched_patterns"],
        "core_evidence": detection["core_evidence"],
        "retrieved_cases": detection["retrieved_cases"],
        "notification": detection["notification"],
    }
