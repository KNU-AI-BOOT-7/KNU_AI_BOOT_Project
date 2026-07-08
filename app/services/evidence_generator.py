"""RAG 탐지 결과를 사람이 이해하기 쉬운 근거 문장으로 생성한다."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from app.schemas import RetrievedCase


logger = logging.getLogger(__name__)


class EvidenceGenerator:
    """생성형 모델을 사용할 수 있으면 사용하고, 아니면 안전한 템플릿을 사용한다."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.base_url = os.getenv("OPENAI_BASE_URL")
        default_model = "openai/gpt-4o-mini" if self._uses_openrouter() else "gpt-4o-mini"
        self.model_name = model_name or os.getenv("LLM_MODEL", default_model)

    def generate(
        self,
        text: str,
        risk_score: float,
        matched_patterns: list[str],
        retrieved_cases: list[RetrievedCase],
    ) -> str:
        """LLM 또는 로컬 대체 템플릿으로 핵심근거를 생성한다."""
        if os.getenv("OPENAI_API_KEY"):
            try:
                return self._generate_with_openai(
                    text=text,
                    risk_score=risk_score,
                    matched_patterns=matched_patterns,
                    retrieved_cases=retrieved_cases,
                )
            except Exception as exc:
                # LLM 장애가 탐지 API 장애로 이어지지 않도록 템플릿 핵심근거로 대체한다.
                logger.warning("OpenAI 근거 생성 실패. 템플릿 근거로 대체합니다: %s", exc)
                return self._generate_template(text, risk_score, matched_patterns, retrieved_cases)

        return self._generate_template(text, risk_score, matched_patterns, retrieved_cases)

    def _generate_with_openai(
        self,
        text: str,
        risk_score: float,
        matched_patterns: list[str],
        retrieved_cases: list[RetrievedCase],
    ) -> str:
        """OpenAI SDK가 설치되고 설정되어 있으면 호출한다."""
        from openai import OpenAI

        context: dict[str, Any] = {
            "input_text": text,
            "risk_score": risk_score,
            "matched_patterns": matched_patterns,
            "retrieved_cases": [case.model_dump() for case in retrieved_cases],
        }

        prompt = f"""
너는 보이스피싱 탐지 시스템의 근거 생성 모듈이다.
아래 JSON만 근거로 사용해서 한국어 설명을 작성하라.

작성 규칙:
- 입력에 없는 사실은 만들지 않는다.
- 단정 대신 "의심된다", "위험 신호가 있다"처럼 신중하게 표현한다.
- 유사 사례 기반 근거와 규칙 기반 위험 신호를 함께 설명한다.
- 마지막에 공식 대표번호로 직접 확인하라는 안전 행동을 제안한다.

JSON:
{json.dumps(context, ensure_ascii=False, indent=2)}
"""

        client = OpenAI(
            base_url=self.base_url,
            default_headers=self._default_headers(),
        )
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": "보이스피싱 탐지 근거를 간결하고 신중하게 작성한다."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def _uses_openrouter(self) -> bool:
        """OpenRouter 호환 엔드포인트를 사용하는지 확인한다."""
        return bool(self.base_url and "openrouter.ai" in self.base_url)

    def _default_headers(self) -> dict[str, str]:
        """OpenRouter에서 권장하는 선택 헤더를 구성한다."""
        if not self._uses_openrouter():
            return {}

        headers: dict[str, str] = {}
        referer = os.getenv("OPENROUTER_HTTP_REFERER")
        title = os.getenv("OPENROUTER_APP_TITLE")

        if referer:
            headers["HTTP-Referer"] = referer
        if title:
            headers["X-Title"] = title

        return headers

    def _generate_template(
        self,
        text: str,
        risk_score: float,
        matched_patterns: list[str],
        retrieved_cases: list[RetrievedCase],
    ) -> str:
        """외부 LLM을 호출하지 않고 핵심근거를 생성한다."""
        risk_percent = round(risk_score * 100, 1)
        phishing_cases = [case for case in retrieved_cases if case.label == 1]

        lines = [f"입력 문장의 보이스피싱 위험도는 {risk_percent}%로 계산되었습니다."]

        if matched_patterns:
            lines.append("탐지된 위험 신호는 " + ", ".join(matched_patterns) + "입니다.")
        else:
            lines.append("명확한 규칙 기반 위험 신호는 적게 탐지되었습니다.")

        if phishing_cases:
            best_case = phishing_cases[0]
            lines.append(
                "DB의 보이스피싱 사례 중 가장 유사한 사례와의 유사도는 "
                f"{round(best_case.similarity * 100, 1)}%입니다."
            )
            lines.append(f"유사 사례 출처는 '{best_case.source or 'unknown'}'입니다.")
        else:
            lines.append("상위 유사 사례에는 보이스피싱 라벨 사례가 많지 않습니다.")

        lines.append("의심되는 경우 통화를 종료하고 기관의 공식 대표번호로 직접 확인하세요.")
        return "\n".join(lines)
