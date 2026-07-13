"""실시간 위험도 탐지: KoELECTRA(1차) → LLM(2차 보강) 2단계 파이프라인.

설계 (recall 우선 — 놓침이 오경보보다 훨씬 비싸다):
  1차 KoELECTRA (매 청크, 로컬, ~수십 ms) — 위험 점수의 주체
    - 누적 전체 문맥과 최근 WINDOW턴 중 높은 확률을 위험도로 사용
      (KoELECTRA는 256토큰 절단이라 긴 통화 후반을 놓칠 수 있어 window 병행)
    - 점수 < LLM_GATE  → 정상 통과 (LLM 호출 안 함, 비용 0)
    - 점수 ≥ LLM_GATE  → 2차로 넘김
  2차 LLM (대화 흐름 판단) — 점수를 올릴 수만 있고 내릴 수 없다 (max 결합)
    - 위험도: final = max(KoELECTRA, LLM). LLM이 KoELECTRA의 경고를 억제하지 못한다.
    - 이유: 이 도메인에서 학습한 KoELECTRA가 대출사기 판별에서 범용 LLM보다 정확하다.
      실측상 LLM에 다운그레이드 권한을 주면 진짜 대출사기(94~99% 확신)를 정상으로
      낮춰 recall이 크게 깨진다. 대신 LLM은 KoELECTRA가 놓친 새 유형을 올려 잡고,
      피싱 판정 시 유형·근거·권장행동을 생성한다 (UI '탐지 근거'용).

경고 기준(기능명세서): 0.70 이상 "주의", 0.85 이상 "강한 경고"

사용 예:
    det = RealtimeDetector(use_llm=True)
    for text in stt_chunks:
        result = det.add(text)         # {"risk_score":0.84,"risk_level":"warning",...}
    final = det.finalize()             # 통화 종료 시 종합 판정

TF-IDF 베이스라인(train_baseline.py)은 런타임에서 제외됐고, KoELECTRA의 가치를
증명하는 '문서화된 대조군'으로만 남는다.
"""
import os

WINDOW = 10          # sliding window 크기 (턴 수)
TH_WARNING = 0.70    # 주의
TH_DANGER = 0.85     # 강한 경고
LLM_GATE = 0.30      # KoELECTRA 점수가 이 이상이면 LLM 2차 판단으로 넘긴다
LLM_RETRY_TURNS = 5  # 같은 통화에서 LLM 재판정 최소 간격 (비용 억제)
LLM_MIN_CHARS = 80   # 문맥이 이보다 짧으면 LLM 호출 안 함 (초반 판정은 부정확)


def level_of(score):
    if score >= TH_DANGER:
        return "danger"
    if score >= TH_WARNING:
        return "warning"
    return "normal"


class RealtimeDetector:
    def __init__(self, use_llm=True):
        self.use_llm = use_llm
        self.turns = []           # text 목록
        self.peak_score = 0.0
        self.llm_result = None
        self.llm_at_turn = None

    def _ke_score(self):
        """1차 KoELECTRA: 누적 vs 최근 WINDOW턴 중 높은 확률."""
        from backend.app.predict_transformer import predict_proba
        cum = " ".join(self.turns)
        win = " ".join(self.turns[-WINDOW:])
        probs = predict_proba([cum, win])
        plain = " ".join(self.turns)
        return float(max(probs)), plain

    def _run_llm(self, context):
        from llm_judge import judge
        result = judge(context)
        if result:
            self.llm_result = result
            self.llm_at_turn = len(self.turns)
        return result

    def _emit(self, score, source):
        self.peak_score = max(self.peak_score, score)
        out = {
            "turn": len(self.turns),
            "risk_score": round(score, 3),
            "risk_level": level_of(score),
            "peak_score": round(self.peak_score, 3),
            "source": source,
        }
        # 점수(max)와 무관하게, LLM이 피싱이라 판단했으면 그 근거를 첨부한다.
        # (KoELECTRA 점수가 더 높아 max로 채택돼도 LLM의 설명은 살린다 — UI '탐지 근거'용)
        if self.llm_result and self.llm_result.get("is_voice_phishing"):
            out["phishing_type"] = self.llm_result.get("phishing_type")
            out["reason"] = self.llm_result.get("reason", [])
            out["recommended_action"] = self.llm_result.get("recommended_action")
        return out

    def _combine(self, ke):
        """final = max(KoELECTRA, LLM). LLM은 점수를 올릴 수만 있다."""
        if self.llm_result:
            llm = float(self.llm_result["risk_score"])
            if llm >= ke:
                return llm, "llm"      # LLM이 더 위험하다고 봄 (근거 첨부됨)
        return ke, "koelectra"

    def add(self, text):
        """새 발화(STT 청크)를 추가하고 현재 위험도를 반환한다."""
        self.turns.append(text)
        ke, plain = self._ke_score()

        # KoELECTRA가 게이트 미만이면 정상 통과 (2차 스킵)
        if not (self.use_llm and ke >= LLM_GATE and len(plain) >= LLM_MIN_CHARS):
            return self._emit(ke, "koelectra")

        # 2차 LLM: 재판정 간격을 두고 호출 (비용 억제)
        stale = self.llm_at_turn is None or len(self.turns) - self.llm_at_turn >= LLM_RETRY_TURNS
        if stale:
            self._run_llm(plain)
        score, source = self._combine(ke)
        return self._emit(score, source)

    def finalize(self):
        """통화 종료 시 종합 판정 (기능명세서 '전체 통화: 최종 판정')."""
        if not self.turns:
            return self._emit(0.0, "koelectra")
        ke, plain = self._ke_score()
        if self.use_llm and ke >= LLM_GATE:
            self._run_llm(plain)
        score, source = self._combine(ke)
        out = self._emit(score, source)
        out["final"] = True
        return out


# ---------- 평가용 ----------

def _eval_stage1():
    """1차 KoELECTRA 단독 성능 (LLM 없이, 빠름)."""
    import json

    from sklearn.model_selection import train_test_split
    from backend.app.predict_transformer import predict_proba, _fmt

    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, "data", "PhishCatch-Data.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    labels = [c["label"] for c in cases]
    _, ev = train_test_split(cases, test_size=0.2, stratify=labels, random_state=42)

    probs = predict_proba([_fmt(c["turns"]) for c in ev])
    fn = [c["id"] for c, p in zip(ev, probs) if c["label"] == 1 and p < TH_WARNING]
    fp = [(c["id"], float(p)) for c, p in zip(ev, probs) if c["label"] == 0 and p >= TH_WARNING]
    n_ph = sum(labels_ := [c["label"] for c in ev])
    print(f"[1차 KoELECTRA 단독] 평가셋 {len(ev)}건 (피싱 {n_ph})")
    print(f"  놓친 피싱(주의 미만): {fn if fn else '없음'}")
    print(f"  정상 오경보(주의 이상): {[(i, f'{p*100:.0f}%') for i, p in fp] if fp else '없음'}")
    return ev, fp


def _eval_cascade_on(ev, fp):
    """2차 LLM이 1차 오경보를 교정하는지 확인 (오경보 케이스만 계단식 재생)."""
    print("\n[2차 LLM 교정 검증] KoELECTRA 오경보 케이스를 계단식으로 재생:")
    id2case = {c["id"]: c for c in ev}
    for cid, ke_p in fp:
        c = id2case[cid]
        det = RealtimeDetector(use_llm=True)
        for t in c["turns"]:
            det.add(t["text"])
        r = det.finalize()
        fixed = "✅ 정상으로 교정" if det.peak_score < TH_WARNING else "❌ 여전히 경고"
        print(f"  {cid}: KoELECTRA {ke_p*100:.0f}% → 최종 {det.peak_score*100:.0f}% ({r['source']}) {fixed}")


if __name__ == "__main__":
    import sys

    ev, fp = _eval_stage1()
    if "cascade" in sys.argv and fp:
        _eval_cascade_on(ev, fp)
