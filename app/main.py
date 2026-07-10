"""보이스피싱 RAG 탐지 API의 FastAPI 진입점."""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import re
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
from app.services.koelectra_scorer import MODEL_DIR, TH_WARNING, KoElectraScorer, risk_level_of
from app.services.rag_detector import RagPhishingDetector


logger = logging.getLogger(__name__)

if load_dotenv:
    load_dotenv()

detector = RagPhishingDetector()
scorer = KoElectraScorer()
_koelectra_missing_logged = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """API 서버가 시작될 때 SQLite DB를 초기화하고 KoELECTRA 모델을 미리 로드"""
    init_db()
    if not scorer.is_ready():
        # 학습 모델이 없으면 원인을 바로 알 수 있도록 warning 로그를 남기고 RAG로 대체한다.
        _log_koelectra_missing()
        yield
        return

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
    클라이언트가 3~4초 단위로 보내는 통화 음성 chunk를 받아 실시간 분석을 수행한다.

    현재 프론트에서 화자 분리를 하지 않으므로, start 이후 mp3/wav 바이너리를
    그대로 받고 서버 전사 결과를 unknown 화자의 발화로 저장한다. 기존 JSON
    텍스트 메시지도 테스트/하위 호환을 위해 유지한다.

    클라이언트 메시지 예시:
    {"type": "start", "device_id": 1, "name": "010-1234-5678", "audio_format": "wav"}
    <3~4초 wav 또는 mp3 바이너리 frame>
    """
    await websocket.accept()
    log_id: Optional[int] = None
    audio_format = "wav"
    chunk_index = 0

    try:
        while True:
            packet = await websocket.receive()

            if packet.get("bytes") is not None:
                if log_id is None:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "오디오 chunk를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다.",
                        }
                    )
                    continue

                chunk_index += 1
                response = await _handle_audio_chunk(
                    log_id=log_id,
                    audio_bytes=packet["bytes"] or b"",
                    audio_format=audio_format,
                    chunk_index=chunk_index,
                )
                await websocket.send_json(response)
                continue

            if packet.get("text") is None:
                await websocket.send_json({"type": "error", "message": "지원하지 않는 WebSocket 메시지입니다."})
                continue

            payload = _parse_ws_json(packet["text"])
            event_type = payload.get("type", "message")

            if event_type == "start":
                audio_format = _normalize_audio_format(str(payload.get("audio_format", audio_format)))
                call = create_call_log(
                    CallLogCreate(
                        device_id=payload.get("device_id"),
                        name=str(payload.get("name", "실시간 통화")),
                        file_type=str(payload.get("file_type", "realtime")),
                    )
                )
                log_id = call.id
                chunk_index = 0
                await websocket.send_json(
                    {
                        "type": "call_started",
                        "call": call.model_dump(),
                        "audio_format": audio_format,
                    }
                )
                continue

            if event_type == "audio_chunk":
                if log_id is None:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "오디오 chunk를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다.",
                        }
                    )
                    continue

                raw_audio = _decode_audio_chunk_payload(payload)
                chunk_index = int(payload.get("chunk_index") or (chunk_index + 1))
                chunk_format = _normalize_audio_format(str(payload.get("audio_format", audio_format)))
                response = await _handle_audio_chunk(
                    log_id=log_id,
                    audio_bytes=raw_audio,
                    audio_format=chunk_format,
                    chunk_index=chunk_index,
                )
                await websocket.send_json(response)
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


async def _handle_audio_chunk(
    log_id: int,
    audio_bytes: bytes,
    audio_format: str,
    chunk_index: int,
) -> dict:
    """실시간 오디오 chunk를 전사하고 누적 통화 분석 응답을 만든다."""
    if not audio_bytes:
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message": "빈 오디오 chunk입니다.",
        }

    try:
        raw_segments = await asyncio.to_thread(_transcribe_audio_bytes, audio_bytes, audio_format)
    except HTTPException as exc:
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message": exc.detail,
        }
    except Exception as exc:
        logger.exception("실시간 오디오 chunk 전사 실패")
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message": f"오디오 chunk 전사에 실패했습니다: {exc}",
        }

    segments = _normalize_transcribed_segments(raw_segments)
    saved_messages = []
    for segment in segments:
        saved_messages.append(
            insert_call_message(
                log_id=log_id,
                message=CallMessageCreate(
                    role=segment["speaker"],
                    content=segment["text"],
                ),
            )
        )

    if not saved_messages:
        return {
            "type": "audio_chunk_ack",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "transcripts": [],
            "message": "전사된 발화가 없습니다.",
        }

    detection = await asyncio.to_thread(_detect_and_persist, log_id=log_id)
    return _build_client_audio_analysis_response(
        log_id=log_id,
        chunk_index=chunk_index,
        saved_messages=[message.model_dump() for message in saved_messages],
        segments=segments,
        detection=detection,
    )


def _transcribe_audio_bytes(audio_bytes: bytes, audio_format: str) -> list[dict]:
    """메모리로 받은 mp3/wav chunk를 임시 파일로 저장한 뒤 전사한다."""
    suffix = f".{_normalize_audio_format(audio_format)}"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.close()
        return _transcribe_audio(tmp.name)
    finally:
        os.unlink(tmp.name)


def _normalize_transcribed_segments(raw_segments: list[dict]) -> list[dict]:
    """전사 모듈별 segment 필드 차이를 API 응답/DB 저장용으로 정규화한다."""
    normalized_segments = []
    for index, segment in enumerate(raw_segments or [], start=1):
        text = str(segment.get("text", segment.get("content", ""))).strip()
        if not text:
            continue

        normalized_segments.append(
            {
                "chunk_id": index,
                "start_time": segment.get("start", segment.get("start_time")),
                "end_time": segment.get("end", segment.get("end_time")),
                "speaker": str(segment.get("speaker", segment.get("role", "unknown")) or "unknown"),
                "text": text,
            }
        )

    return normalized_segments


def _parse_ws_json(raw_text: str) -> dict:
    """WebSocket text frame을 JSON 객체로 변환한다."""
    import json

    try:
        payload = json.loads(raw_text)
    except Exception as exc:
        raise ValueError("WebSocket text frame은 JSON 형식이어야 합니다.") from exc

    if not isinstance(payload, dict):
        raise ValueError("WebSocket JSON 메시지는 객체여야 합니다.")

    return payload


def _decode_audio_chunk_payload(payload: dict) -> bytes:
    """base64 JSON 방식으로 전달된 오디오 chunk를 디코딩한다."""
    encoded_audio = str(payload.get("audio_base64", "")).strip()
    if not encoded_audio:
        raise ValueError("audio_chunk 메시지에는 audio_base64가 필요합니다.")

    try:
        return base64.b64decode(encoded_audio, validate=True)
    except Exception as exc:
        raise ValueError("audio_base64를 디코딩할 수 없습니다.") from exc


def _normalize_audio_format(audio_format: str) -> str:
    """프론트에서 넘긴 오디오 포맷명을 mp3 또는 wav로 정규화한다."""
    normalized = audio_format.lower().strip().lstrip(".")
    if normalized in {"mpeg", "mpga"}:
        normalized = "mp3"

    if normalized not in {"mp3", "wav"}:
        raise ValueError("audio_format은 mp3 또는 wav만 지원합니다.")

    return normalized


def _detect_and_persist(log_id: int, top_k: int = 5) -> dict:
    """
    누적 통화 내용을 탐지하고 결과와 필요 알림 이력을 DB에 저장한다.

    위험도 점수는 KoELECTRA가 전담하고, RAG/규칙 탐지는 근거와 키워드 생성에 사용한다.
    """
    call_text = build_call_text(log_id)
    koelectra_score = _score_with_koelectra(log_id)
    if koelectra_score is not None:
        preliminary_patterns = detector.rule_detector.find(call_text)
        koelectra_score = _calibrate_koelectra_score(
            text=call_text,
            raw_score=koelectra_score,
            matched_patterns=preliminary_patterns,
        )

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
    if not scorer.is_ready():
        _log_koelectra_missing()
        return None

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


def _build_client_audio_analysis_response(
    log_id: int,
    chunk_index: int,
    saved_messages: list[dict],
    segments: list[dict],
    detection: dict,
) -> dict:
    """실시간 오디오 chunk 전사/분석 결과를 클라이언트 응답 형태로 만든다."""
    base_response = {
        "log_id": log_id,
        "chunk_index": chunk_index,
        "message_ids": [message["id"] for message in saved_messages],
        "transcripts": [
            {
                "message_id": message["id"],
                "turn_index": message["turn_index"],
                "role": message["role"],
                "content": message["content"],
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
            }
            for message, segment in zip(saved_messages, segments)
        ],
        "is_phishing": detection["is_phishing"],
        "risk_score": detection["risk_score"],
        "risk_level": detection["risk_level"],
        "phishing_type": detection["phishing_type"],
    }

    if not detection["is_phishing"]:
        return {
            "type": "audio_analysis_ack",
            **base_response,
        }

    return {
        "type": "audio_phishing_detected",
        **base_response,
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


def _log_koelectra_missing() -> None:
    """KoELECTRA 모델 미설정 상태를 서버 로그에 한 번만 명확히 남긴다."""
    global _koelectra_missing_logged
    if _koelectra_missing_logged:
        return

    _koelectra_missing_logged = True
    logger.warning(
        "KoELECTRA 모델 폴더가 없어 KoELECTRA 위험도 계산을 사용하지 않습니다. "
        "현재 요청은 RAG/규칙 기반 점수로 대체됩니다. "
        "학습 후 모델을 생성하세요. model_dir=%s",
        MODEL_DIR,
    )


def _calibrate_koelectra_score(text: str, raw_score: float, matched_patterns: list[str]) -> float:
    """
    KoELECTRA가 정상 금융상담을 피싱으로 과탐지하는 경우를 보정한다.

    예: "비밀번호나 인증번호를 요구하지 않습니다"처럼 위험 키워드가 들어 있지만
    실제 의미는 안전 안내인 문장은 모델 점수를 낮춘다.
    """
    if raw_score < TH_WARNING:
        return raw_score

    if _has_strong_phishing_context(matched_patterns):
        return raw_score

    if not _has_normal_finance_context(text):
        return raw_score

    logger.info(
        "정상 금융상담 문맥으로 KoELECTRA 점수를 보정합니다. raw_score=%.4f calibrated_score=0.4200",
        raw_score,
    )
    return min(raw_score, 0.42)


def _has_strong_phishing_context(matched_patterns: list[str]) -> bool:
    """명확한 피싱 조합이면 정상 상담 보정을 적용하지 않는다."""
    matched = set(matched_patterns)

    if "수사기관/공공기관 사칭" in matched and (
        "범죄 연루 압박" in matched or "금전 이체 유도" in matched
    ):
        return True

    if "대출 사칭/상환금 요구" in matched and "금전 이체 유도" in matched:
        return True

    if "개인정보/인증 요구" in matched and "앱 설치/원격제어 유도" in matched:
        return True

    if "금전 이체 유도" in matched and "긴급성/비밀 유지 압박" in matched:
        return True

    return False


def _has_normal_finance_context(text: str) -> bool:
    """정상 계좌 개설/상담에서 자주 나오는 안전 문맥을 찾는다."""
    safe_patterns = [
        r"계좌\s*개설.*문의",
        r"비대면\s*계좌\s*개설",
        r"본인인증\s*후\s*진행",
        r"신분증만\s*준비",
        r"앱에서도\s*확인",
        r"공식\s*앱",
        r"상담원.*(비밀번호|인증번호).*요구하지",
        r"(비밀번호|인증번호).*요구하지",
    ]
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in safe_patterns)
