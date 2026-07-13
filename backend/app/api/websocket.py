"""실시간 통화 오디오 분석 WebSocket 라우터."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from backend.app.repository import create_call_log, insert_call_message
from backend.app.schemas import CallLogCreate, CallMessageCreate
from backend.app.services import audio_transcriber, call_analyzer


logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/calls/analyze")
async def analyze_call_messages(websocket: WebSocket) -> None:
    """
    클라이언트가 3~4초 단위로 보내는 통화 음성 chunk를 받아 실시간 분석을 수행한다.

    start 이후 m4a 바이너리 chunk를 그대로 받고 서버 전사 결과를 발화 내용으로 저장한다.
    mp3/wav도 테스트/호환 목적으로 지원하며, 기존 JSON 텍스트 메시지도 유지한다.
    """
    await websocket.accept()
    log_id: Optional[int] = None
    audio_format = "m4a"
    chunk_index = 0

    try:
        while True:
            packet = await websocket.receive()
            if packet.get("type") == "websocket.disconnect":
                return

            if packet.get("bytes") is not None:
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
                if not await _send_json(websocket, {"type": "error", "message": "지원하지 않는 WebSocket 메시지입니다."}):
                    return
                continue

            payload = _parse_ws_json(packet["text"])
            event_type = payload.get("type", "message")

            if event_type == "start":
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
    if not audio_bytes:
        return {
            "type": "audio_chunk_error",
            "log_id": log_id,
            "chunk_index": chunk_index,
            "message": "빈 오디오 chunk입니다.",
        }

    try:
        raw_segments = await asyncio.to_thread(audio_transcriber.transcribe_audio_bytes, audio_bytes, audio_format)
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

    segments = audio_transcriber.normalize_transcribed_segments(raw_segments)
    saved_messages = []
    for segment in segments:
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
            "transcripts": [],
            "message": "전사된 발화가 없습니다.",
        }

    detection = await asyncio.to_thread(call_analyzer.detect_and_persist, log_id=log_id)
    return call_analyzer.build_client_audio_analysis_response(
        log_id=log_id,
        chunk_index=chunk_index,
        saved_messages=[message.model_dump() for message in saved_messages],
        segments=segments,
        detection=detection,
    )


def _parse_ws_json(raw_text: str) -> dict:
    """WebSocket text frame을 JSON 객체로 변환한다."""
    try:
        payload = json.loads(raw_text)
    except Exception as exc:
        raise ValueError("WebSocket text frame은 JSON 형식이어야 합니다.") from exc

    if not isinstance(payload, dict):
        raise ValueError("WebSocket JSON 메시지는 객체여야 합니다.")

    return payload
