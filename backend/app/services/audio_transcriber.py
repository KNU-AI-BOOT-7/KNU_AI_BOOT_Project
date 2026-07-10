"""오디오 전사와 실시간 chunk 입력 정규화 서비스."""

from __future__ import annotations

import base64
import os
import tempfile

from fastapi import HTTPException


def transcribe_audio_file(audio_path: str) -> list[dict]:
    """오디오 파일을 전사 모듈에 넘겨 발화 segment 목록으로 변환한다."""
    try:
        from backend.app.mp3_json import transcribe_with_speakers
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=501,
            detail="오디오 전사 모듈(backend.app.mp3_json)이 아직 설정되어 있지 않습니다.",
        ) from exc

    return transcribe_with_speakers(audio_path)


def transcribe_audio_bytes(audio_bytes: bytes, audio_format: str) -> list[dict]:
    """메모리로 받은 mp3/wav chunk를 임시 파일로 저장한 뒤 전사한다."""
    suffix = f".{normalize_audio_format(audio_format)}"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(audio_bytes)
        tmp.close()
        return transcribe_audio_file(tmp.name)
    finally:
        os.unlink(tmp.name)


def normalize_transcribed_segments(raw_segments: list[dict]) -> list[dict]:
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


def decode_audio_chunk_payload(payload: dict) -> bytes:
    """base64 JSON 방식으로 전달된 오디오 chunk를 디코딩한다."""
    encoded_audio = str(payload.get("audio_base64", "")).strip()
    if not encoded_audio:
        raise ValueError("audio_chunk 메시지에는 audio_base64가 필요합니다.")

    try:
        return base64.b64decode(encoded_audio, validate=True)
    except Exception as exc:
        raise ValueError("audio_base64를 디코딩할 수 없습니다.") from exc


def normalize_audio_format(audio_format: str) -> str:
    """프론트에서 넘긴 오디오 포맷명을 mp3 또는 wav로 정규화한다."""
    normalized = audio_format.lower().strip().lstrip(".")
    if normalized in {"mpeg", "mpga"}:
        normalized = "mp3"

    if normalized not in {"mp3", "wav"}:
        raise ValueError("audio_format은 mp3 또는 wav만 지원합니다.")

    return normalized
