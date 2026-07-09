"""LLM 기반 보이스피싱 판정 (기능명세서 3.6 '3차 AI 판단').

베이스라인이 애매하게 본 케이스(30~85%)의 최종 판정과 탐지 근거 문장 생성을 담당한다.
OpenRouter API 사용, 키는 .env의 OPENROUTER_API_KEY.

사용 예:
    from llm_judge import judge
    result = judge("검찰청입니다 본인 계좌가 범죄에 연루되어...")
    # {"is_voice_phishing": true, "risk_score": 0.9, "reason": [...], ...}
"""
import json
import os

from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL = os.environ.get("LLM_JUDGE_MODEL", "anthropic/claude-haiku-4.5")
MAX_CHARS = 4000  # 긴 통화는 최근 내용 위주로 자름

SYSTEM_PROMPT = """너는 보이스피싱 탐지 전문가다. 통화 전사 텍스트를 보고 보이스피싱 여부를 판정한다.

[피싱 신호 — 대화 흐름에서 이런 패턴을 찾아라]
- 수사기관/금융기관 사칭 + 범죄 연루, 계좌 동결 등으로 협박
- 지정 계좌(안전계좌)로 이체 요구, 현금 인출 유도
- 비밀 유지 강요 (가족/은행/경찰에 말하지 말라)
- 시간 압박 (지금 당장, 오늘 안에, 안 하면 취소/체포)
- 원격제어 앱, 문자 링크로 앱 설치 유도
- 비밀번호, 인증번호, 카드번호 요구
- 대출 승인 조건으로 기존 대출 선상환, 선입금 요구
- 가족·지인을 납치/감금했다고 협박하며 금전을 요구하거나 신고를 막음 (납치 협박형)

[수사기관 사칭 초기 징후 — 아직 금전 요구가 없어도 위험하다]
통화 초반에는 계좌 이체·개인정보 요구가 아직 안 나올 수 있다. 다음이 보이면 구체적
금전 요구가 없더라도 수사기관 사칭형으로 보고 risk_score를 0.6 이상으로 평가하라.
- 화자가 스스로 검찰/경찰/수사관/금융감독원 소속이라 주장하거나 관등성명·사건번호를 반복 강조
- 상대방을 사건에 연루시키거나 신고 접수·조사 대상이라 통보하며 불안을 조성
- 징역/벌금/체포 등 법적 처벌 가능성을 언급하며 강압적 어조로 압박
※ 단, 화자가 '제3자의 사기를 조심하라'고 경고하면서 공식 대표번호로 직접 확인하라고
   안내하는 것은 정상적인 예방 안내다 (사칭이 아님).

[정상 신호 — 이런 패턴은 합법적 금융 영업/안내다]
- 공식 앱, 지점 방문, 대표번호로 안내하고 고객이 직접 처리하게 함
- "천천히 결정하세요", 거절을 수용하는 태도
- 입출금은 본인 명의 계좌로만 처리
- 정상적인 대출/보험/카드 권유 전화(텔레마케팅)는 피싱이 아니다
- 은행·기관이 '보이스피싱을 조심하라'고 예방 교육하는 통화는 정상이다

반드시 아래 JSON 형식으로만 답하라. 다른 텍스트는 출력하지 마라.
{"is_voice_phishing": true/false, "risk_score": 0.0~1.0, "phishing_type": "수사기관 사칭형"|"대출 사기형"|"납치 협박형"|"기타"|null, "reason": ["근거 1", "근거 2"], "recommended_action": "사용자에게 권장할 행동 한 문장"}"""


def _load_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        with open(os.path.join(BASE_DIR, ".env"), encoding="utf-8") as f:
            for line in f:
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip()
    return key


_client = None


def _extract_json(raw):
    """모델 응답에서 JSON 객체를 견고하게 추출한다.
    코드펜스·설명 문장이 섞여 나와도 가장 바깥 { ... }를 파싱한다."""
    raw = raw.strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"JSON 객체 없음: {raw[:80]!r}")
    return json.loads(raw[start:end + 1])


def judge(transcript, retries=1):
    """통화 전사 텍스트를 LLM으로 판정한다. 실패 시 None 반환 (호출측에서 KoELECTRA 점수로 폴백)."""
    global _client
    if _client is None:
        _client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=_load_key())
    text = transcript[-MAX_CHARS:]
    last_err = None
    for _ in range(retries + 1):
        try:
            r = _client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"다음 통화 내용을 판정하라:\n\n{text}"},
                ],
                temperature=0,
                max_tokens=500,
            )
            return _extract_json(r.choices[0].message.content or "")
        except Exception as e:
            last_err = e
    print(f"[llm_judge] 판정 실패: {last_err}")
    return None


if __name__ == "__main__":
    demo = ("안녕하세요 고객님 저는 국민은행 대출 상담사입니다 지난주에 홈페이지로 "
            "전세자금대출 상담 신청을 해주셔서 연락드렸습니다 가까운 지점 방문이나 "
            "공식 앱으로 신청 가능하십니다 천천히 검토해 보세요")
    print(json.dumps(judge(demo), ensure_ascii=False, indent=2))
