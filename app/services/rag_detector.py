"""RAG 기반 보이스피싱 탐지 서비스."""

from __future__ import annotations

import math
import re
from collections import Counter

from app.repository import list_all_training_cases
from app.schemas import RagDetectResponse, RetrievedCase
from app.services.evidence_generator import EvidenceGenerator


class RuleSignalDetector:
    """입력 문장에서 설명 가능한 보이스피싱 위험 신호를 찾는다."""

    PATTERNS: dict[str, list[str]] = {
        "수사기관/공공기관 사칭": [
            r"검찰",
            r"경찰",
            r"금융감독원",
            r"금감원",
            r"법원",
            r"수사관",
        ],
        "범죄 연루 압박": [
            r"범죄.*연루",
            r"대포통장",
            r"명의.*도용",
            r"구속",
            r"체포",
            r"영장",
        ],
        "금전 이체 유도": [
            r"안전계좌",
            r"이체",
            r"송금",
            r"입금",
            r"현금.*인출",
        ],
        "개인정보/인증 요구": [
            r"주민등록번호",
            r"계좌번호",
            r"비밀번호",
            r"인증번호",
            r"OTP",
        ],
        "앱 설치/원격제어 유도": [
            r"앱.*설치",
            r"원격",
            r"원격제어",
            r"URL",
            r"링크.*클릭",
        ],
        "긴급성/비밀 유지 압박": [
            r"지금.*바로",
            r"즉시",
            r"오늘.*안",
            r"비밀",
            r"말하지.*마",
        ],
    }

    def find(self, text: str) -> list[str]:
        """탐지된 위험 신호 그룹 이름을 반환한다."""
        matched: list[str] = []
        for pattern_name, regexes in self.PATTERNS.items():
            if any(re.search(regex, text, flags=re.IGNORECASE) for regex in regexes):
                matched.append(pattern_name)
        return matched


class RagPhishingDetector:
    """
    DB에서 유사 사례를 검색하고 근거를 생성해 보이스피싱을 탐지한다.

    이 구현은 벡터 DB 없이도 실행할 수 있도록 순수 파이썬 문자 n-gram
    유사도를 사용한다. 추후 API를 바꾸지 않고 FAISS, Chroma,
    Elasticsearch 같은 검색 방식으로 교체할 수 있다.
    """

    def __init__(self) -> None:
        self.rule_detector = RuleSignalDetector()
        self.evidence_generator = EvidenceGenerator()

    def detect(self, text: str, top_k: int = 5) -> RagDetectResponse:
        """RAG 검색, 점수 계산, 근거 생성을 실행한다."""
        cleaned_text = self._clean_text(text)
        if not cleaned_text:
            raise ValueError("탐지할 텍스트가 비어 있습니다.")

        retrieved_cases = self._retrieve_similar_cases(cleaned_text, top_k)
        matched_patterns = self.rule_detector.find(cleaned_text)
        risk_score = self._calculate_risk_score(retrieved_cases, matched_patterns)
        risk_level = self._risk_level(risk_score)
        evidence = self.evidence_generator.generate(
            text=cleaned_text,
            risk_score=risk_score,
            matched_patterns=matched_patterns,
            retrieved_cases=retrieved_cases,
        )

        return RagDetectResponse(
            is_phishing=risk_score >= 0.6,
            risk_level=risk_level,
            risk_score=round(risk_score, 4),
            matched_patterns=matched_patterns,
            core_evidence=evidence,
            retrieved_cases=retrieved_cases,
        )

    def _retrieve_similar_cases(self, query: str, top_k: int) -> list[RetrievedCase]:
        """문자 n-gram 코사인 유사도로 DB 사례를 검색한다."""
        cases = list_all_training_cases()
        query_vector = self._char_ngram_counter(query)
        scored_cases: list[RetrievedCase] = []

        for case in cases:
            case_vector = self._char_ngram_counter(case.text)
            similarity = self._cosine_similarity(query_vector, case_vector)
            scored_cases.append(
                RetrievedCase(
                    id=case.id,
                    external_id=case.external_id,
                    text=case.text,
                    label=case.label,
                    source=case.source,
                    similarity=round(similarity, 4),
                )
            )

        scored_cases.sort(key=lambda item: item.similarity, reverse=True)
        return scored_cases[:top_k]

    def _calculate_risk_score(
        self,
        retrieved_cases: list[RetrievedCase],
        matched_patterns: list[str],
    ) -> float:
        """
        검색된 보이스피싱 사례와 규칙 신호로 위험 점수를 계산한다.

        - RAG 점수 70%: 검색된 보이스피싱 사례 중 가장 높은 유사도
        - 규칙 점수 30%: 탐지된 위험 신호 그룹 개수
        """
        phishing_similarity = 0.0
        for case in retrieved_cases:
            if case.label == 1:
                phishing_similarity = max(phishing_similarity, case.similarity)

        rule_score = min(len(matched_patterns) / 5, 1.0)
        score = (phishing_similarity * 0.7) + (rule_score * 0.3)
        return max(0.0, min(score, 1.0))

    def _char_ngram_counter(self, text: str, min_n: int = 2, max_n: int = 5) -> Counter[str]:
        """텍스트를 문자 n-gram 카운트 벡터로 변환한다."""
        normalized = self._clean_text(text)
        padded = f" {normalized} "
        grams: Counter[str] = Counter()

        for n in range(min_n, max_n + 1):
            for index in range(0, max(len(padded) - n + 1, 0)):
                grams[padded[index : index + n]] += 1

        return grams

    def _cosine_similarity(self, left: Counter[str], right: Counter[str]) -> float:
        """두 희소 Counter 벡터의 코사인 유사도를 계산한다."""
        if not left or not right:
            return 0.0

        common_keys = set(left) & set(right)
        dot_product = sum(left[key] * right[key] for key in common_keys)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot_product / (left_norm * right_norm)

    def _risk_level(self, risk_score: float) -> str:
        """숫자 위험 점수를 간단한 위험 등급으로 변환한다."""
        if risk_score >= 0.75:
            return "high"
        if risk_score >= 0.45:
            return "medium"
        return "low"

    def _clean_text(self, text: str) -> str:
        """원문 한국어는 유지하면서 반복 공백만 정규화한다."""
        return re.sub(r"\s+", " ", text).strip()
