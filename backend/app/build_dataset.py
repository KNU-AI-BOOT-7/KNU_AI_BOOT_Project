"""data/ 아래 4가지 형식의 JSON을 통합 형식으로 변환한다.

출력: data/PhishCatch-Data.json
  {"cases": [{"id", "label", "turns": [{"turn_index", "text"}]}]}
  label: 피싱 1, 정상 0
"""
import json
import glob
import os
import re

from backend.app.paths import DATA_DIR


OUT_PATH = os.path.join(DATA_DIR, "PhishCatch-Data.json")

# 피싱 전사본은 실명·기관명을 O/X/* 로 마스킹했으나 정상/실제 STT에는 없다.
# 이 마스킹 토큰만 골라 제거해 모델이 "O/X = 피싱" 지름길을 학습하는 것을 막는다.
# (ㅇㅇ류는 정상 통화의 실제 추임새라 건드리지 않는다. 숫자는 보존.)
_MASK_RUN = re.compile(r"[oOxX]{2,}")                 # OO, XXX, OOO씨 등
_MASK_SOLO = re.compile(r"(?<![A-Za-z])[OX](?![A-Za-z])")  # 한글 사이 단독 O/X
_MASK_SYMBOL = re.compile(r"[*※#]{2,}")               # ***, ※※ 등

# 데이터 수집 과정에서 새어든 아티팩트 (피싱 전사에만 존재, 정상 0건).
# 실제 통화 내용이 아니므로 제거한다. 방치 시 모델이 이 문구를 피싱 신호로 암기한다.
#  - STT 전사 지시문: "...관련 용어에 유의해 정확히 전사하세요." (피싱 124건)
#  - 유튜브 자막 보일러플레이트: "자막이 필요하면 댓글에 링크를 적어주세요." (피싱)
_ARTIFACT_STT = re.compile(r"[^.!?]*전사(?:하세요|해\s*주세요)[.!?]?")
_ARTIFACT_YT = re.compile(r"자막이 필요하면 댓글에 링크를 적어주세요\.?")
_WS = re.compile(r"\s{2,}")


def clean_mask(text):
    """마스킹 토큰과 수집 아티팩트를 제거한다. 남은 실제 신호(경찰서, 씨 등)는 보존."""
    text = _ARTIFACT_STT.sub(" ", text)
    text = _ARTIFACT_YT.sub(" ", text)
    text = _MASK_RUN.sub(" ", text)
    text = _MASK_SOLO.sub(" ", text)
    text = _MASK_SYMBOL.sub(" ", text)
    return _WS.sub(" ", text).strip()


def make_case(case_id, label, raw_turns):
    """raw_turns: 텍스트 목록. 빈 텍스트는 제외."""
    turns = []
    for text in raw_turns:
        text = clean_mask(text.strip())
        if not text:
            continue
        turns.append({
            "turn_index": len(turns) + 1,
            "text": text,
        })
    return {"id": case_id, "label": label, "turns": turns}


def load_phishing():
    sources = {
        "그놈 목소리(수사기관 사칭형)": "susagigwan",
        "그놈 목소리(대출 사기형)": "daechul",
        "바로 이 목소리": "baro",
    }
    cases = []
    for folder, code in sources.items():
        path = os.path.join(DATA_DIR, "phishing", folder, "dataset.json")
        with open(path, encoding="utf-8") as f:
            calls = json.load(f)
        for i, call in enumerate(calls, 1):
            segs = sorted(call["segments"], key=lambda s: s["chunk_id"])
            raw = [s["text"] for s in segs]
            cases.append(make_case(f"phishing_{code}_{i:04d}", 1, raw))
        print(f"phishing/{folder}: {len(calls)}건")
    return cases


def load_finance():
    path = os.path.join(DATA_DIR, "normal", "금융상담 데이터셋", "D61_금융상담_dataset.json")
    with open(path, encoding="utf-8") as f:
        sessions = json.load(f)
    cases = []
    for i, sess in enumerate(sessions, 1):
        dialogue = sorted(sess["dialogue"], key=lambda t: t["turn"])
        raw = [t["text"] for t in dialogue]
        cases.append(make_case(f"normal_finance_{i:04d}", 0, raw))
    print(f"normal/금융상담: {len(sessions)}건")
    return cases


def load_free_talk():
    cases = []
    for sub, code in [("VL_01.실내", "indoor"), ("VL_02.실외", "outdoor")]:
        paths = sorted(glob.glob(os.path.join(DATA_DIR, "normal", "자유대화", sub, "*.json")))
        for i, path in enumerate(paths, 1):
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            conv = sorted(d["Conversation"], key=lambda t: int(t["TextNo"]))
            raw = [t["Text"] for t in conv]
            cases.append(make_case(f"normal_free_{code}_{i:04d}", 0, raw))
        print(f"normal/자유대화/{sub}: {len(paths)}건")
    return cases


def load_outbound():
    """직접 작성한 정상 아웃바운드 권유 전화 시나리오 (하드 네거티브)."""
    scripts = []
    for fname in ["outbound_scripts.json", "outbound_scripts2.json"]:
        with open(os.path.join(DATA_DIR, "normal", fname), encoding="utf-8") as f:
            scripts += json.load(f)
    cases = []
    for i, s in enumerate(scripts, 1):
        turns = []
        for turn in s["turns"]:
            if isinstance(turn, dict):
                turns.append(turn["text"])
            elif isinstance(turn, list) and len(turn) >= 2:
                turns.append(turn[1])
            else:
                turns.append(str(turn))
        cases.append(make_case(f"normal_outbound_{i:04d}", 0, turns))
    print(f"normal/outbound_scripts(작성): {len(scripts)}건")
    return cases


def main():
    cases = load_phishing() + load_finance() + load_free_talk() + load_outbound()

    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "id 중복 발생"
    empty = [c["id"] for c in cases if not c["turns"]]
    if empty:
        print(f"경고: 발화가 없는 케이스 {len(empty)}건 제외: {empty[:5]}")
        cases = [c for c in cases if c["turns"]]

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"cases": cases}, f, ensure_ascii=False, indent=2)

    n_phish = sum(1 for c in cases if c["label"] == 1)
    n_normal = len(cases) - n_phish
    n_turns = sum(len(c["turns"]) for c in cases)
    size_mb = os.path.getsize(OUT_PATH) / 1024 / 1024
    print(f"\n완료: {OUT_PATH} ({size_mb:.1f}MB)")
    print(f"  전체 {len(cases)}건 = 피싱 {n_phish} + 정상 {n_normal} / 총 발화 {n_turns:,}턴")


if __name__ == "__main__":
    main()
