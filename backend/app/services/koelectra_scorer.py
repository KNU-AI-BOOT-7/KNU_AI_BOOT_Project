"""KoELECTRA fine-tuned 모델 기반 위험도 채점 서비스.

역할 분담 (탐지 파이프라인):
  - 위험 점수(risk_score) 산출은 이 모듈이 전담한다.
  - 룰 매칭(matched_patterns), RAG 유사 사례(retrieved_cases), 근거 문장(core_evidence)은
    기존 RagPhishingDetector / EvidenceGenerator가 설명 전용으로 계속 담당한다.

입력 포맷:
  화자 구분 없이 발화 내용을 순서대로 공백 연결해 사용한다.
"""

from __future__ import annotations

from backend.app.paths import KOELECTRA_MODEL_DIR

WINDOW = 10  # 최근 N턴 sliding window (256토큰 절단으로 긴 통화 후반을 놓치는 것 방지)
MODEL_DIR = KOELECTRA_MODEL_DIR

# 기능명세서 경고 기준: 0.70 이상 "주의", 0.85 이상 "강한 경고"
TH_WARNING = 0.70
TH_DANGER = 0.85


def risk_level_of(score: float) -> str:
    """점수를 기존 API 어휘(high/medium/low)로 변환한다. high=강한경고, medium=주의."""
    if score >= TH_DANGER:
        return "high"
    if score >= TH_WARNING:
        return "medium"
    return "low"


class KoElectraScorer:
    """models/koelectra 를 1회 로드해 통화 발화 목록의 피싱 확률을 계산한다."""

    def is_ready(self) -> bool:
        """학습된 KoELECTRA 모델 폴더가 있으면 True를 반환한다."""
        return MODEL_DIR.exists()

    def preload(self) -> None:
        """서버 시작 시 모델을 미리 로드해 첫 요청 지연을 없앤다."""
        self._ensure_model_ready()
        from backend.app.predict_transformer import predict_proba

        predict_proba(["로드 확인"])

    def score(self, messages) -> float:
        """통화 발화 목록(content 속성 필요)의 피싱 확률을 반환한다.

        누적 전체 문맥과 최근 WINDOW턴 중 높은 확률을 사용한다.
        """
        if not messages:
            return 0.0

        self._ensure_model_ready()
        from backend.app.predict_transformer import predict_proba

        contents = [str(message.content).strip() for message in messages if str(message.content).strip()]
        if not contents:
            return 0.0

        cumulative = " ".join(contents)
        window = " ".join(contents[-WINDOW:])
        probs = predict_proba([cumulative, window])
        return float(max(probs))

    def _ensure_model_ready(self) -> None:
        """KoELECTRA 모델 파일이 없으면 추론 대신 RAG fallback을 사용하도록 알린다."""
        if not self.is_ready():
            raise RuntimeError(f"{MODEL_DIR} 모델 폴더가 없습니다.")
