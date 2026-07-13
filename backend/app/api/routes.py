"""REST API 라우터."""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.app.api.response_logger import log_api_request, log_api_response
from backend.app.repository import (
    create_call_log,
    get_call_conversation_response,
    get_call_log_detail_response,
    get_call_log_list_response,
    insert_call_message,
    insert_training_cases,
    list_training_cases,
    parse_training_cases_json,
)
from backend.app.schemas import (
    CallConversationResponse,
    CallLogCreate,
    CallLogDetail,
    CallLogListResponse,
    CallMessageCreate,
    ImportResult,
    TrainingCase,
)
from backend.app.services import audio_transcriber, call_analyzer


router = APIRouter()


def _optional_int(value: object, field_name: str) -> Optional[int]:
    """multipart form/query에서 넘어온 선택 정수 값을 안전하게 변환한다."""
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field_name}는 정수여야 합니다.") from exc


@router.get("/health")
def health() -> dict[str, str]:
    """서버 상태 확인 엔드포인트."""
    return log_api_response("GET /health", {"status": "ok"})


@router.get("/calls", response_model=CallLogListResponse)
def get_calls(limit: int = 100, device_id: Optional[int] = None) -> CallLogListResponse:
    """통화 기록 목록과 리스크 레벨별 개수를 반환한다."""
    response = get_call_log_list_response(limit=limit, device_id=device_id)
    return log_api_response("GET /calls", response)


@router.get("/calls/{log_id}", response_model=CallLogDetail)
def get_call_detail(log_id: int) -> CallLogDetail:
    """단일 통화 기록의 피싱 유형, 주요 키워드, 근거를 반환한다."""
    try:
        response = get_call_log_detail_response(log_id=log_id)
        return log_api_response("GET /calls/{log_id}", response)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/calls/{log_id}/messages", response_model=CallConversationResponse)
def get_call_messages(log_id: int) -> CallConversationResponse:
    """단일 통화 기록에 저장된 대화 내역을 반환한다."""
    try:
        response = get_call_conversation_response(log_id=log_id)
        return log_api_response("GET /calls/{log_id}/messages", response)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/training-cases/import-json", response_model=ImportResult)
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
        call_analyzer.clear_detector_index()
    response = ImportResult(inserted_count=inserted_count, skipped_count=skipped_count)
    return log_api_response("POST /training-cases/import-json", response)


@router.get("/training-cases", response_model=list[TrainingCase])
def get_training_cases(limit: int = 100) -> list[TrainingCase]:
    """최근 저장된 학습 사례를 반환한다."""
    response = list_training_cases(limit=limit)
    return log_api_response("GET /training-cases", response)


@router.post("/calls/analyze-audio")
async def analyze_call_audio(
    request: Request,
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
    if suffix not in (".mp3", ".wav", ".m4a"):
        raise HTTPException(status_code=400, detail="mp3, wav, m4a 파일만 업로드할 수 있습니다.")

    form = await request.form()
    form_device_id = _optional_int(form.get("device_id"), "device_id")
    form_top_k = _optional_int(form.get("top_k"), "top_k")
    if form_device_id is not None:
        device_id = form_device_id
    if form_top_k is not None:
        top_k = form_top_k

    raw_bytes = await file.read()
    log_api_request(
        "POST /calls/analyze-audio",
        {
            "file_name": file.filename,
            "client_host": request.client.host if request.client else None,
            "device_id": device_id,
            "top_k": top_k,
            "audio_format": suffix.lstrip("."),
            "byte_size": len(raw_bytes),
        },
    )
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(raw_bytes)
        tmp.close()
        try:
            raw_segments = await asyncio.to_thread(audio_transcriber.transcribe_audio_file, tmp.name)
        except HTTPException as exc:
            log_api_response(
                "POST /calls/analyze-audio",
                {
                    "type": "audio_analysis_error",
                    "status_code": exc.status_code,
                    "file_name": file.filename,
                    "message": exc.detail,
                },
            )
            raise
        except Exception as exc:
            log_api_response(
                "POST /calls/analyze-audio",
                {
                    "type": "audio_analysis_error",
                    "status_code": 422,
                    "file_name": file.filename,
                    "message": f"오디오 파일을 전사하지 못했습니다: {exc}",
                },
            )
            raise HTTPException(
                status_code=422,
                detail=f"오디오 파일을 전사하지 못했습니다: {exc}",
            ) from exc
    finally:
        os.unlink(tmp.name)

    segments = audio_transcriber.normalize_transcribed_segments(raw_segments)
    if not segments:
        log_api_response(
            "POST /calls/analyze-audio",
            {
                "type": "audio_analysis_error",
                "status_code": 422,
                "file_name": file.filename,
                "raw_segment_count": len(raw_segments or []),
                "message": "오디오에서 발화를 전사하지 못했습니다.",
            },
        )
        raise HTTPException(status_code=422, detail="오디오에서 발화를 전사하지 못했습니다.")

    call = create_call_log(
        CallLogCreate(
            device_id=device_id,
            name=file.filename or "업로드 통화",
            file_type="recording",
        )
    )
    saved_messages = []
    for turn_index, segment in enumerate(segments, start=1):
        saved_messages.append(
            insert_call_message(
                log_id=call.id,
                message=CallMessageCreate(
                    content=segment["text"],
                    turn_index=turn_index,
                ),
            )
        )

    detection = await asyncio.to_thread(call_analyzer.detect_and_persist, log_id=call.id, top_k=top_k)
    converted_text = audio_transcriber.join_transcript_texts(
        [message.content for message in saved_messages]
    )
    log_api_request(
        "POST /calls/analyze-audio",
        {
            "log_id": call.id,
            "message_count": len(saved_messages),
            "message_id_first": saved_messages[0].id if saved_messages else None,
            "message_id_last": saved_messages[-1].id if saved_messages else None,
            "converted_text": converted_text,
        },
    )

    response = {
        "type": "audio_analysis",
        "log_id": call.id,
        "file_name": file.filename,
        "message_count": len(saved_messages),
        "message_ids": [message.id for message in saved_messages],
        "converted_text": converted_text,
        "transcripts": [
            {
                "message_id": message.id,
                "turn_index": message.turn_index,
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
            }
            for message, segment in zip(saved_messages, segments)
        ],
        "segments": segments,
        "is_phishing": detection["is_phishing"],
        "risk_score": detection["risk_score"],
        "risk_level": detection["risk_level"],
        "phishing_type": detection["phishing_type"],
        "matched_patterns": detection["matched_patterns"],
        "core_evidence": detection["core_evidence"],
        "notification": detection["notification"],
    }
    return log_api_response("POST /calls/analyze-audio", response)
