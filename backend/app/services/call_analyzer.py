"""통화 누적 내용 분석, 탐지 결과 저장, 클라이언트 응답 생성 서비스."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from backend.app.repository import (
    build_call_text,
    get_call_log,
    insert_notification,
    list_call_messages,
    save_detection_result,
)
from backend.app.schemas import NotificationCreate
from backend.app.services.koelectra_scorer import MODEL_DIR, TH_WARNING, KoElectraScorer, risk_level_of
from backend.app.services.rag_detector import RagPhishingDetector


logger = logging.getLogger(__name__)

detector = RagPhishingDetector()
scorer = KoElectraScorer()
_koelectra_missing_logged = False


async def preload_koelectra_model() -> None:
    """서버 시작 시 KoELECTRA 모델을 미리 로드한다."""
    if not scorer.is_ready():
        _log_koelectra_missing()
        return

    try:
        await asyncio.to_thread(scorer.preload)
    except Exception as exc:
        logger.warning("KoELECTRA 모델 사전 로드 실패. RAG 점수로 대체합니다: %s", exc)


def clear_detector_index() -> None:
    """학습 사례가 바뀌었을 때 RAG 인덱스 캐시를 비운다."""
    detector.clear_index()


def detect_and_persist(log_id: int, top_k: int = 5) -> dict:
    """
    누적 통화 내용을 탐지하고 결과와 필요 알림 이력을 DB에 저장한다.

    위험도 점수는 KoELECTRA가 우선 담당하고, RAG/규칙 탐지는 근거와 키워드 생성에 사용한다.
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


def build_client_text_analysis_response(log_id: int, message: dict, detection: dict) -> dict:
    """테스트/하위 호환용 텍스트 발화 분석 응답을 만든다."""
    if not detection["is_phishing"]:
        return {
            "type": "analysis_ack",
            "log_id": log_id,
            "message_id": message["id"],
            "converted_text": message["content"],
            "is_phishing": False,
            "risk_score": detection["risk_score"],
            "risk_level": detection["risk_level"],
            "phishing_type": detection["phishing_type"],
        }

    return {
        "type": "phishing_detected",
        "log_id": log_id,
        "message_id": message["id"],
        "converted_text": message["content"],
        "is_phishing": True,
        "risk_score": detection["risk_score"],
        "risk_level": detection["risk_level"],
        "phishing_type": detection["phishing_type"],
        "matched_patterns": detection["matched_patterns"],
        "core_evidence": detection["core_evidence"],
        "notification": detection["notification"],
    }


def build_client_audio_analysis_response(
    log_id: int,
    chunk_index: int,
    saved_messages: list[dict],
    segments: list[dict],
    detection: dict,
) -> dict:
    """실시간 오디오 chunk 전사/분석 결과를 클라이언트 응답 형태로 만든다."""
    converted_text = "\n".join(message["content"] for message in saved_messages)
    base_response = {
        "log_id": log_id,
        "chunk_index": chunk_index,
        "message_ids": [message["id"] for message in saved_messages],
        "converted_text": converted_text,
        "transcripts": [
            {
                "message_id": message["id"],
                "turn_index": message["turn_index"],
                "content": message["content"],
                "converted_text": message["content"],
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
