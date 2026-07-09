"""KoELECTRA fine-tuned 모델 기반 위험도 채점 서비스.

역할 분담 (탐지 파이프라인):
  - 위험 점수(risk_score) 산출은 이 모듈이 전담한다.
  - 룰 매칭(matched_patterns), RAG 유사 사례(retrieved_cases), 근거 문장(core_evidence)은
    기존 RagPhishingDetector / EvidenceGenerator가 설명 전용으로 계속 담당한다.

입력 포맷 주의:
  모델은 "[A] 발화 [B] 발화 ..." 형태(화자 태그 + 공백 연결)로 학습됐다 (train_transformer.py).
  role 문자열(caller/receiver/speaker_a 등)이 무엇이든, 통화 안에서의 등장 순서로
  첫 화자=[A], 둘째 화자=[B]로 매핑해야 학습 분포와 일치한다 (build_dataset.py와 동일 규칙).
"""

from __future__ import annotations

from pathlib import Path

WINDOW = 10  # 최근 N턴 sliding window (256토큰 절단으로 긴 통화 후반을 놓치는 것 방지)
MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "koelectra"

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

    def preload(self) -> None:
        """서버 시작 시 모델을 미리 로드해 첫 요청 지연을 없앤다."""
        self._ensure_model_ready()
        from predict_transformer import predict_proba

        predict_proba(["[A] 로드 확인"])

    def score(self, messages) -> float:
        """통화 발화 목록(role/content 속성 필요)의 피싱 확률을 반환한다.

        누적 전체 문맥과 최근 WINDOW턴 중 높은 확률을 사용한다.
        """
        if not messages:
            return 0.0

        self._ensure_model_ready()
        from predict_transformer import predict_proba

        speaker_map: dict[str, str] = {}
        tagged: list[str] = []
        for message in messages:
            role = str(message.role)
            if role not in speaker_map:
                speaker_map[role] = chr(ord("A") + len(speaker_map))
            tagged.append(f"[{speaker_map[role]}] {message.content}")

        cumulative = " ".join(tagged)
        window = " ".join(tagged[-WINDOW:])
        probs = predict_proba([cumulative, window])
        return float(max(probs))

    def _ensure_model_ready(self) -> None:
        """KoELECTRA 모델 파일이 없으면 추론 대신 RAG fallback을 사용하도록 알린다."""
        if not MODEL_DIR.exists():
            raise RuntimeError(f"{MODEL_DIR} 모델 폴더가 없습니다.")
