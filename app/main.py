"""보이스피싱 RAG 탐지 API의 FastAPI 진입점."""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

from app.database import init_db
from app.repository import (
    build_call_text,
    create_call_log,
    get_call_log_detail_response,
    get_call_log_list_response,
    get_call_log,
    insert_call_message,
    insert_notification,
    insert_training_cases,
    list_call_messages,
    list_training_cases,
    parse_training_cases_json,
    save_detection_result,
)
from app.schemas import (
    CallLogDetail,
    CallLogListResponse,
    CallLogCreate,
    CallMessageCreate,
    ImportResult,
    NotificationCreate,
    TrainingCase,
)
from app.services.koelectra_scorer import TH_WARNING, KoElectraScorer, risk_level_of
from app.services.rag_detector import RagPhishingDetector


logger = logging.getLogger(__name__)

if load_dotenv:
    load_dotenv()

detector = RagPhishingDetector()
scorer = KoElectraScorer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """API 서버가 시작될 때 SQLite DB를 초기화하고 KoELECTRA 모델을 미리 로드"""
    init_db()
    try:
        await asyncio.to_thread(scorer.preload)
    except Exception as exc:
        # 모델 파일이나 torch/transformers가 없는 개발 환경에서도 RAG API는 계속 실행되게 한다.
        logger.warning("KoELECTRA 모델 사전 로드 실패. RAG 점수로 대체합니다: %s", exc)
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


@app.get("/calls", response_model=CallLogListResponse)
def get_calls(limit: int = 100) -> CallLogListResponse:
    """통화 기록 목록과 리스크 레벨별 개수를 반환한다."""
    return get_call_log_list_response(limit=limit)


@app.get("/calls/{log_id}", response_model=CallLogDetail)
def get_call_detail(log_id: int) -> CallLogDetail:
    """단일 통화 기록의 피싱 유형, 주요 키워드, 근거를 반환한다."""
    try:
        return get_call_log_detail_response(log_id=log_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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
    if inserted_count > 0:
        detector.clear_index()
    return ImportResult(inserted_count=inserted_count, skipped_count=skipped_count)


@app.get("/training-cases", response_model=list[TrainingCase])
def get_training_cases(limit: int = 100) -> list[TrainingCase]:
    """최근 저장된 학습 사례를 반환한다."""
    return list_training_cases(limit=limit)


@app.post("/calls/analyze-audio")
async def analyze_call_audio(
    file: UploadFile = File(...),
    device_id: Optional[int] = None,
    top_k: int = 5,
) -> dict:
    """
    통화 녹음 파일을 업로드받아 전사 후 보이스피싱 여부를 분석한다.

    추후 녹음 파일 분석 화면에서 사용할 API이며, 저장 구조는 실시간 분석과 동일하게
    call_logs, call_messages, detection_results를 재사용한다.
    """
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".mp3", ".wav"):
        raise HTTPException(status_code=400, detail="mp3 또는 wav 파일만 업로드할 수 있습니다.")

    raw_bytes = await file.read()
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(raw_bytes)
        tmp.close()
        segments = await asyncio.to_thread(_transcribe_audio, tmp.name)
    finally:
        os.unlink(tmp.name)

    if not segments:
        raise HTTPException(status_code=422, detail="오디오에서 발화를 전사하지 못했습니다.")

    call = create_call_log(
        CallLogCreate(
            device_id=device_id,
            name=file.filename or "업로드 통화",
            file_type="recording",
        )
    )
    for turn_index, segment in enumerate(segments, start=1):
        insert_call_message(
            log_id=call.id,
            message=CallMessageCreate(
                role=str(segment["speaker"]),
                content=str(segment["text"]),
                turn_index=turn_index,
            ),
        )

    detection = await asyncio.to_thread(_detect_and_persist, log_id=call.id, top_k=top_k)

    return {
        "type": "audio_analysis",
        "log_id": call.id,
        "file_name": file.filename,
        "segments": [
            {
                "chunk_id": index + 1,
                "start_time": segment["start"],
                "end_time": segment["end"],
                "speaker": segment["speaker"],
                "text": segment["text"],
            }
            for index, segment in enumerate(segments)
        ],
        "is_phishing": detection["is_phishing"],
        "risk_score": detection["risk_score"],
        "risk_level": detection["risk_level"],
        "phishing_type": detection["phishing_type"],
        "matched_patterns": detection["matched_patterns"],
        "core_evidence": detection["core_evidence"],
        "notification": detection["notification"],
    }


def _transcribe_audio(audio_path: str) -> list[dict]:
    """오디오 파일을 화자별 발화 segment 목록으로 전사한다."""
    try:
        from mp3_json import transcribe_with_speakers
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=501,
            detail="오디오 전사 모듈(mp3_json)이 아직 설정되어 있지 않습니다.",
        ) from exc

    return transcribe_with_speakers(audio_path)


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
                        file_type=str(payload.get("file_type", "realtime")),
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
            detection = await asyncio.to_thread(
                _detect_and_persist,
                log_id=log_id,
                top_k=int(payload.get("top_k", 5)),
            )
            response = _build_client_analysis_response(log_id, saved_message.model_dump(), detection)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        return
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()


def _detect_and_persist(log_id: int, top_k: int = 5) -> dict:
    """
    누적 통화 내용을 탐지하고 결과와 필요 알림 이력을 DB에 저장한다.

    위험도 점수는 KoELECTRA가 전담하고, RAG/규칙 탐지는 근거와 키워드 생성에 사용한다.
    """
    call_text = build_call_text(log_id)
    koelectra_score = _score_with_koelectra(log_id)
    detection = detector.detect(
        text=call_text,
        top_k=top_k,
        risk_score_override=koelectra_score,
    )
    if koelectra_score is None:
        risk_score = detection.risk_score
        risk_level = detection.risk_level
        is_phishing = detection.is_phishing
        model_version = "rag-v1"
    else:
        risk_score = koelectra_score
        risk_level = risk_level_of(koelectra_score)
        is_phishing = koelectra_score >= TH_WARNING
        model_version = "koelectra-v1"

    detected_label = 1 if is_phishing else 0
    retrieved_case_ids = [case.id for case in detection.retrieved_cases]
    previous_level = get_call_log(log_id).risk_level

    saved_result = save_detection_result(
        log_id=log_id,
        risk_score=risk_score,
        risk_level=risk_level,
        detected_label=detected_label,
        core_evidence=detection.core_evidence,
        matched_patterns=detection.matched_patterns,
        retrieved_case_ids=retrieved_case_ids,
        model_version=model_version,
    )

    notification = None
    if risk_level == "high" and previous_level != "high":
        notification = insert_notification(
            log_id=log_id,
            notification=NotificationCreate(
                reason=detection.core_evidence,
                message="보이스피싱 위험이 높게 탐지되었습니다. 통화를 종료하고 공식 대표번호로 확인하세요.",
                status="sent",
            ),
        )

    latest_call = get_call_log(log_id)

    return {
        "is_phishing": is_phishing,
        "risk_level": risk_level,
        "risk_score": round(risk_score, 4),
        "phishing_type": latest_call.phishing_type,
        "matched_patterns": detection.matched_patterns,
        "core_evidence": detection.core_evidence,
        "saved_result": saved_result.model_dump(),
        "notification": _compact_notification(notification.model_dump()) if notification else None,
    }


def _score_with_koelectra(log_id: int) -> Optional[float]:
    """KoELECTRA 모델이 준비되어 있으면 위험도 점수를 계산하고, 실패 시 None을 반환한다."""
    try:
        return scorer.score(list_call_messages(log_id))
    except Exception as exc:
        logger.warning("KoELECTRA 점수 계산 실패. RAG 점수로 대체합니다: %s", exc)
        return None


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
            "message_id": message["id"],
            "is_phishing": False,
            "risk_score": detection["risk_score"],
            "risk_level": detection["risk_level"],
            "phishing_type": detection["phishing_type"],
        }

    return {
        "type": "phishing_detected",
        "log_id": log_id,
        "message_id": message["id"],
        "is_phishing": True,
        "risk_score": detection["risk_score"],
        "risk_level": detection["risk_level"],
        "phishing_type": detection["phishing_type"],
        "matched_patterns": detection["matched_patterns"],
        "core_evidence": detection["core_evidence"],
        "notification": detection["notification"],
    }


def _compact_notification(notification: dict) -> dict:
    """클라이언트 응답에는 알림 표시용 최소 필드만 포함한다."""
    return {
        "id": notification["id"],
        "message": notification["message"],
        "status": notification["status"],
        "created_at": notification["created_at"],
    }
