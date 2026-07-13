"""API 응답 payload를 서버 로그에서 확인하기 위한 도우미."""

from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger("uvicorn.error")


def log_api_response(endpoint: str, payload: Any) -> Any:
    """응답 payload를 로깅하고 원본 payload를 그대로 반환한다."""
    try:
        logger.info(
            "%s response=%s",
            endpoint,
            json.dumps(_to_loggable(payload), ensure_ascii=False, default=str),
        )
    except Exception:
        logger.exception("%s 응답 로깅 실패", endpoint)

    return payload


def log_api_request(endpoint: str, payload: Any) -> Any:
    """요청 payload를 로깅하고 원본 payload를 그대로 반환한다."""
    try:
        logger.info(
            "%s request=%s",
            endpoint,
            json.dumps(_to_loggable(payload), ensure_ascii=False, default=str),
        )
    except Exception:
        logger.exception("%s 요청 로깅 실패", endpoint)

    return payload


def _to_loggable(value: Any) -> Any:
    """Pydantic 모델과 중첩 리스트/딕셔너리를 로그용 값으로 변환한다."""
    if hasattr(value, "model_dump"):
        return _to_loggable(value.model_dump())

    if isinstance(value, dict):
        return {
            key: _summarize_large_value(key, item)
            for key, item in value.items()
        }

    if isinstance(value, bytes):
        return f"<bytes length={len(value)}>"

    if isinstance(value, list):
        return [_to_loggable(item) for item in value[:3]]

    if isinstance(value, tuple):
        return [_to_loggable(item) for item in value[:3]]

    return value


def _summarize_large_value(key: Any, value: Any) -> Any:
    """오디오 원문처럼 큰 값은 길이만 남긴다."""
    if key == "audio_base64" and isinstance(value, str):
        return f"<base64 length={len(value)}>"

    if isinstance(value, bytes):
        return f"<bytes length={len(value)}>"

    return _to_loggable(value)
