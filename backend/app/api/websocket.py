"""실시간 통화 오디오 분석 WebSocket 라우터."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.app.api.response_logger import log_api_request, log_api_response
from backend.app.repository import create_call_log, get_call_log, insert_call_message, list_call_messages
from backend.app.schemas import CallLogCreate, CallMessageCreate
from backend.app.services import audio_transcriber, call_analyzer


logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/calls/analyze")
async def analyze_call_messages(websocket: WebSocket) -> None:
    """
    클라이언트가 3~4초 단위로 보내는 통화 음성 chunk를 받아 실시간 분석을 수행한다.

    start는 통화 로그만 생성한다. 이후 오디오 chunk를 전사한 뒤 전사된 문장을 저장한다.
    mp3/wav도 테스트/호환 목적으로 지원하며, 기존 JSON 텍스트 메시지도 유지한다.
    """
    await websocket.accept()
    log_id: Optional[int] = None
    audio_format = "m4a"
    chunk_index = 0
    client_host = websocket.client.host if websocket.client else None

    try:
        while True:
            packet = await websocket.receive()
            if packet.get("type") == "websocket.disconnect":
                return

            if packet.get("bytes") is not None:
                incoming_chunk_index = chunk_index + 1 if log_id is not None else None
                log_api_request(
                    "WS /ws/calls/analyze",
                    {
                        "frame": "bytes",
                        "log_id": log_id,
                        "client_host": client_host,
                        "chunk_index": incoming_chunk_index,
                        "audio_format": audio_format,
                        "byte_size": len(packet["bytes"] or b""),
                    },
                )
                if log_id is None:
                    if not await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": "오디오 chunk를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다.",
                        }
                    ):
                        return
                    continue

                chunk_index += 1
                response = await _handle_audio_chunk(
                    log_id=log_id,
                    audio_bytes=packet["bytes"] or b"",
                    audio_format=audio_format,
                    chunk_index=chunk_index,
                )
                if not await _send_json(websocket, response):
                    return
                continue

            if packet.get("text") is None:
                log_api_request(
                    "WS /ws/calls/analyze",
                    {
                        "frame": str(packet.get("type", "unknown")),
                        "log_id": log_id,
                        "client_host": client_host,
                    },
                )
                if not await _send_json(websocket, {"type": "error", "message": "지원하지 않는 WebSocket 메시지입니다."}):
                    return
                continue

            payload = _parse_ws_json(packet["text"])
            event_type = payload.get("type", "message")
            log_api_request(
                "WS /ws/calls/analyze",
                {
                    "frame": "text",
                    "log_id": log_id,
                    "client_host": client_host,
                    "event_type": event_type,
                    "payload": payload,
                },
            )

            if event_type == "start":
                if "file_type" not in payload:
                    if not await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": "start 메시지에는 file_type='realtime'이 필요합니다. 프론트 번들이 오래됐거나 fipe 오타를 보내고 있습니다.",
                        },
                    ):
                        return
                    continue

                audio_format = audio_transcriber.normalize_audio_format(str(payload.get("audio_format", audio_format)))
                call = create_call_log(
                    CallLogCreate(
                        device_id=payload.get("device_id"),
                        name=str(payload.get("name", "실시간 통화")),
                        file_type=str(payload.get("file_type", "realtime")),
                    )
                )
                log_id = call.id
                chunk_index = 0
                if not await _send_json(
                    websocket,
                    {
                        "type": "call_started",
                        "call": call.model_dump(),
                        "audio_format": audio_format,
                    }
                ):
                    return
                continue

            if event_type == "audio_chunk":
                if log_id is None:
                    if not await _send_json(
                        websocket,
                        {
                            "type": "error",
                            "message": "오디오 chunk를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다.",
                        }
                    ):
                        return
                    continue

                raw_audio = audio_transcriber.decode_audio_chunk_payload(payload)
                chunk_index = int(payload.get("chunk_index") or (chunk_index + 1))
                chunk_format = audio_transcriber.normalize_audio_format(str(payload.get("audio_format", audio_format)))
                response = await _handle_audio_chunk(
                    log_id=log_id,
                    audio_bytes=raw_audio,
                    audio_format=chunk_format,
                    chunk_index=chunk_index,
                )
                if not await _send_json(websocket, response):
                    return
                continue

            if event_type != "message":
                if not await _send_json(websocket, {"type": "error", "message": "지원하지 않는 메시지 타입입니다."}):
                    return
                continue

            if log_id is None:
                if not await _send_json(
                    websocket,
                    {
                        "type": "error",
                        "message": "통화 발화를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다.",
                    }
                ):
                    return
                continue

            saved_message = insert_call_message(
                log_id=log_id,
                message=CallMessageCreate(
                    content=str(payload.get("content", "")),
                    turn_index=payload.get("turn_index"),
                ),
            )
            detection = await asyncio.to_thread(
                call_analyzer.detect_and_persist,
                log_id=log_id,
                top_k=int(payload.get("top_k", 5)),
            )
            response = call_analyzer.build_client_text_analysis_response(
                log_id,
                saved_message.model_dump(),
                detection,
            )
            if not await _send_json(websocket, response):
                return
    except WebSocketDisconnect:
        return
    except Exception as exc:
        logger.exception("WebSocket 실시간 분석 처리 실패")
        await _send_json(websocket, {"type": "error", "message": str(exc)})
        await _close_websocket(websocket)


async def _send_json(websocket: WebSocket, payload: dict) -> bool:
    """닫혔거나 닫히는 중인 WebSocket에는 응답을 보내지 않는다."""
    try:
        log_api_response("WS /ws/calls/analyze", payload)
        await websocket.send_json(payload)
        return True
    except (RuntimeError, WebSocketDisconnect):
        logger.info("이미 종료된 WebSocket이라 응답 전송을 생략합니다.")
        return False


async def _close_websocket(websocket: WebSocket) -> None:
    """이미 닫힌 WebSocket close 시도를 조용히 무시한다."""
    try:
        await websocket.close()
    except RuntimeError:
        return


async def _handle_audio_chunk(
    log_id: int,
    audio_bytes: bytes,
    audio_format: str,
    chunk_index: int,
) -> dict:
    """실시간 오디오 chunk를 전사하고 누적 통화 분석 응답을 만든다."""
    started_at = time.monotonic()
    if not audio_bytes:
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message_count": 0,
            **_current_risk_fields(log_id),
            "message": "빈 오디오 chunk입니다.",
        }

    try:
        raw_segments = await asyncio.to_thread(audio_transcriber.transcribe_audio_bytes, audio_bytes, audio_format)
        transcribed_at = time.monotonic()
    except HTTPException as exc:
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message_count": 0,
            **_current_risk_fields(log_id),
            "message": exc.detail,
        }
    except Exception as exc:
        logger.exception("실시간 오디오 chunk 전사 실패")
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message_count": 0,
            **_current_risk_fields(log_id),
            "message": f"오디오 chunk 전사에 실패했습니다: {exc}",
        }

    segments = audio_transcriber.normalize_transcribed_segments(raw_segments)
    segments, skipped_duplicate_count = _filter_duplicate_segments(log_id, segments)
    saved_messages = []
    for segment in segments:
        # 전사가 성공한 segment만 call_messages에 저장한다.
        saved_messages.append(
            insert_call_message(
                log_id=log_id,
                message=CallMessageCreate(
                    content=segment["text"],
                ),
            )
        )

    if not saved_messages:
        return {
            "type": "audio_chunk_ack",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message_count": 0,
            "converted_text": "",
            "transcripts": [],
            "skipped_duplicate_count": skipped_duplicate_count,
            **_current_risk_fields(log_id),
            "message": "전사된 발화가 없습니다." if skipped_duplicate_count == 0 else "중복 전사로 판단되어 저장하지 않았습니다.",
        }

    detection = await asyncio.to_thread(
        call_analyzer.detect_and_persist,
        log_id=log_id,
        use_llm_evidence=False,
    )
    analyzed_at = time.monotonic()
    response = call_analyzer.build_client_audio_analysis_response(
        log_id=log_id,
        chunk_index=chunk_index,
        saved_messages=[message.model_dump() for message in saved_messages],
        segments=segments,
        detection=detection,
    )
    response["skipped_duplicate_count"] = skipped_duplicate_count
    response["latency_ms"] = {
        "stt": round((transcribed_at - started_at) * 1000),
        "analysis": round((analyzed_at - transcribed_at) * 1000),
        "total": round((analyzed_at - started_at) * 1000),
    }
    return response


def _parse_ws_json(raw_text: str) -> dict:
    """WebSocket text frame을 JSON 객체로 변환한다."""
    try:
        payload = json.loads(raw_text)
    except Exception as exc:
        raise ValueError("WebSocket text frame은 JSON 형식이어야 합니다.") from exc

    if not isinstance(payload, dict):
        raise ValueError("WebSocket JSON 메시지는 객체여야 합니다.")

    return payload


def _current_risk_fields(log_id: int) -> dict:
    """분석을 새로 못 한 응답에도 현재 통화 위험도 필드를 포함한다."""
    try:
        call = get_call_log(log_id)
    except Exception:
        return {"risk_score": 0.0, "risk_level": "low"}

    return {
        "risk_score": round(call.risk_score, 4),
        "risk_level": call.risk_level,
    }


def _filter_duplicate_segments(log_id: int, segments: list[dict]) -> tuple[list[dict], int]:
    """최근 저장된 긴 전사 문장이 반복되면 저장 대상에서 제외한다.

    오디오 청크를 겹쳐(overlap) 보내므로, 새 세그먼트 앞부분이 직전 문장 끝과
    실제로 겹쳐서 들어온다. 겹치는 부분을 먼저 잘라낸 뒤 완전 중복 여부를 판단한다.
    """
    if not segments:
        return [], 0

    recent_messages = list_call_messages(log_id)[-120:]
    recent_texts = {_normalize_duplicate_key(message.content) for message in recent_messages}
    last_text = recent_messages[-1].content if recent_messages else ""
    kept_segments = []
    skipped_count = 0

    for segment in segments:
        original_text = str(segment.get("text", ""))
        stripped_text = _strip_overlap_prefix(last_text, original_text)
        duplicate_key = _normalize_duplicate_key(stripped_text)

        if not stripped_text or (duplicate_key and duplicate_key in recent_texts):
            skipped_count += 1
            continue

        kept_segments.append({**segment, "text": stripped_text})
        last_text = original_text  # 다음 세그먼트와의 겹침은 원본(자르기 전) 기준으로 비교
        if duplicate_key:
            recent_texts.add(duplicate_key)

    return kept_segments, skipped_count


def _strip_overlap_prefix(previous_text: str, new_text: str, min_overlap: int = 6) -> str:
    """오디오 겹침으로 new_text 앞부분이 previous_text 끝부분과 겹치면 그 부분을 잘라낸다.

    이전 시도들의 문제:
    - 단순 "prev의 끝 L글자 == curr의 앞 L글자" 완전일치 방식은, 겹친 오디오를 두 번
      다르게 전사하면("가능하신" vs "가능하실까요") 끝까지 정확히 일치하는 길이가
      없어서 못 잡는다.
    - 공백 기준 단어 단위 비교는 겹침이 단어 중간에서 잘리면("대출관리팀" →
      "관리팀"부터 시작) 아예 못 잡는다.
    그래서 prev의 꼬리를 여러 길이 L로 잘라가며 curr 시작 부분과 "앞에서부터 몇 글자나
    일치하는지"를 전부 계산하고, 그중 가장 길게 일치하는 지점을 겹침으로 본다. 일치가
    길수록 진짜 겹침일 확률이 높으므로, 충분히 긴 일치(min_overlap)만 인정해 "습니다"
    같은 흔한 어미의 우연한 일치는 걸러낸다.
    """
    prev = previous_text.strip()
    curr = new_text.strip()
    if not prev or not curr:
        return curr

    best_match = 0
    max_len = min(len(prev), len(curr))
    for length in range(1, max_len + 1):
        window = prev[-length:]
        matched = _shared_prefix_len(window, curr)
        if matched > best_match:
            best_match = matched

    if best_match >= min_overlap:
        return curr[best_match:].strip()
    return curr


def _shared_prefix_len(a: str, b: str) -> int:
    """두 문자열이 앞에서부터 몇 글자나 같은지 센다."""
    length = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        length += 1
    return length


def _normalize_duplicate_key(text: str) -> str:
    """짧은 맞장구는 제외하고, 의미 있는 길이의 반복 문장만 중복 키로 사용한다."""
    normalized = " ".join(text.split()).strip()
    if len(normalized) < 8:
        return ""
    return normalized
