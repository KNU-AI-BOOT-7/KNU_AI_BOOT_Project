"""RAG 기반 보이스피싱 탐지 서비스."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from threading import Lock
from typing import Optional

from app.repository import list_all_training_cases
from app.schemas import RagDetectResponse, RetrievedCase
from app.services.evidence_generator import EvidenceGenerator


@dataclass(frozen=True)
class IndexedTrainingCase:
    """RAG 검색 속도를 높이기 위해 미리 계산해 둔 학습 사례 벡터."""

    case: RetrievedCase
    vector: Counter[str]
    vector_norm: float


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
        "대출 사칭/상환금 요구": [
            r"저금리",
            r"정부지원.*대출",
            r"대출.*승인",
            r"기존.*대출.*상환",
            r"상환금",
            r"지정.*계좌",
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
        self._indexed_cases: Optional[list[IndexedTrainingCase]] = None
        self._index_lock = Lock()

    def clear_index(self) -> None:
        """학습 데이터가 바뀌었을 때 다음 검색에서 RAG 인덱스를 다시 만들도록 비운다."""
        with self._index_lock:
            self._indexed_cases = None

    def detect(self, text: str, top_k: int = 5) -> RagDetectResponse:
        """RAG 검색, 점수 계산, 근거 생성을 실행한다."""
        cleaned_text = self._clean_text(text)
        if not cleaned_text:
            raise ValueError("탐지할 텍스트가 비어 있습니다.")

        matched_patterns = self.rule_detector.find(cleaned_text)
        # 강한 피싱 조합은 규칙만으로도 충분히 위험하므로 RAG 검색을 생략해 응답 시간을 줄인다.
        if self._should_skip_rag_for_strong_signal(matched_patterns):
            retrieved_cases: list[RetrievedCase] = []
        else:
            retrieved_cases = self._retrieve_similar_cases(cleaned_text, top_k)

        risk_score = self._calculate_risk_score(
            text=cleaned_text,
            retrieved_cases=retrieved_cases,
            matched_patterns=matched_patterns,
        )
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
        """캐시된 문자 n-gram 벡터로 DB 유사 사례를 검색한다."""
        query_vector = self._char_ngram_counter(query)
        query_norm = self._counter_norm(query_vector)
        scored_cases: list[RetrievedCase] = []

        for indexed_case in self._get_indexed_cases():
            similarity = self._cosine_similarity(
                left=query_vector,
                right=indexed_case.vector,
                left_norm=query_norm,
                right_norm=indexed_case.vector_norm,
            )
            case = indexed_case.case
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

    def _get_indexed_cases(self) -> list[IndexedTrainingCase]:
        """학습 사례를 한 번만 읽고 n-gram 벡터를 메모리에 캐싱한다."""
        if self._indexed_cases is not None:
            return self._indexed_cases

        with self._index_lock:
            if self._indexed_cases is not None:
                return self._indexed_cases

            indexed_cases: list[IndexedTrainingCase] = []
            for case in list_all_training_cases():
                # 긴 통화 전문 전체를 벡터화하면 첫 검색이 느려지므로 검색용 텍스트만 압축해서 사용한다.
                vector = self._char_ngram_counter(self._search_text(case.text))
                indexed_cases.append(
                    IndexedTrainingCase(
                        case=RetrievedCase(
                            id=case.id,
                            external_id=case.external_id,
                            text=case.text,
                            label=case.label,
                            source=case.source,
                            similarity=0.0,
                        ),
                        vector=vector,
                        vector_norm=self._counter_norm(vector),
                    )
                )

            self._indexed_cases = indexed_cases
            return indexed_cases

    def _calculate_risk_score(
        self,
        text: str,
        retrieved_cases: list[RetrievedCase],
        matched_patterns: list[str],
    ) -> float:
        """
        검색된 보이스피싱 사례와 규칙 신호로 위험 점수를 계산한다.

        - RAG 점수 50%: 검색된 보이스피싱 사례 중 가장 높은 유사도
        - 규칙 점수 50%: 탐지된 위험 신호 그룹 개수
        - 강한 피싱 조합은 RAG 유사도가 낮아도 최소 위험도를 보정
        - 공식 채널 안내 같은 정상 상담 신호는 강한 조합이 없을 때만 감점
        """
        phishing_similarity = 0.0
        for case in retrieved_cases:
            if case.label == 1:
                phishing_similarity = max(phishing_similarity, case.similarity)

        rule_score = min(len(matched_patterns) / 5, 1.0)
        score = (phishing_similarity * 0.5) + (rule_score * 0.5)
        strong_combo_floor = self._strong_phishing_combo_floor(matched_patterns)

        if strong_combo_floor > 0:
            score = max(score, strong_combo_floor)
        else:
            score -= self._normal_consulting_discount(text)

        return max(0.0, min(score, 1.0))

    def _strong_phishing_combo_floor(self, matched_patterns: list[str]) -> float:
        """핵심 위험 신호 조합이면 RAG 유사도와 무관하게 최소 점수를 부여한다."""
        matched = set(matched_patterns)
        has_combo = False

        if "수사기관/공공기관 사칭" in matched and (
            "범죄 연루 압박" in matched or "금전 이체 유도" in matched
        ):
            has_combo = True

        if "대출 사칭/상환금 요구" in matched and "금전 이체 유도" in matched:
            has_combo = True

        if "개인정보/인증 요구" in matched and "앱 설치/원격제어 유도" in matched:
            has_combo = True

        if "금전 이체 유도" in matched and "긴급성/비밀 유지 압박" in matched:
            has_combo = True

        if not has_combo:
            return 0.0

        if len(matched) >= 3:
            return 0.82
        return 0.72

    def _should_skip_rag_for_strong_signal(self, matched_patterns: list[str]) -> bool:
        """강한 피싱 조합이 이미 잡혔으면 실시간 응답을 위해 RAG 검색을 건너뛴다."""
        return self._strong_phishing_combo_floor(matched_patterns) > 0

    def _normal_consulting_discount(self, text: str) -> float:
        """정상 금융 상담에서 자주 나오는 안전 신호가 있으면 위험도를 낮춘다."""
        safe_patterns = [
            r"공식\s*앱",
            r"지점.*방문",
            r"천천히.*검토",
            r"오늘.*결정.*안",
            r"상담.*신청",
            r"서류.*심사",
            r"부담.*갖지",
            r"다시.*연락",
        ]
        safe_count = sum(
            1 for pattern in safe_patterns if re.search(pattern, text, flags=re.IGNORECASE)
        )
        return min(safe_count * 0.04, 0.18)

    def _char_ngram_counter(self, text: str, min_n: int = 2, max_n: int = 5) -> Counter[str]:
        """텍스트를 문자 n-gram 카운트 벡터로 변환한다."""
        normalized = self._clean_text(text)
        padded = f" {normalized} "
        grams: Counter[str] = Counter()

        for n in range(min_n, max_n + 1):
            for index in range(0, max(len(padded) - n + 1, 0)):
                grams[padded[index : index + n]] += 1

        return grams

    def _cosine_similarity(
        self,
        left: Counter[str],
        right: Counter[str],
        left_norm: Optional[float] = None,
        right_norm: Optional[float] = None,
    ) -> float:
        """두 희소 Counter 벡터의 코사인 유사도를 계산한다."""
        if not left or not right:
            return 0.0

        common_keys = set(left) & set(right)
        dot_product = sum(left[key] * right[key] for key in common_keys)
        left_norm = left_norm if left_norm is not None else self._counter_norm(left)
        right_norm = right_norm if right_norm is not None else self._counter_norm(right)

        if left_norm == 0 or right_norm == 0:
            return 0.0

        return dot_product / (left_norm * right_norm)

    def _counter_norm(self, vector: Counter[str]) -> float:
        """코사인 유사도 계산에 쓰는 벡터 크기를 계산한다."""
        return math.sqrt(sum(value * value for value in vector.values()))

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

    def _search_text(self, text: str, max_length: int = 1200) -> str:
        """RAG 검색 벡터 생성에 사용할 길이를 제한한다."""
        cleaned_text = self._clean_text(text)
        if len(cleaned_text) <= max_length:
            return cleaned_text
        return cleaned_text[:max_length].rstrip()
