"""KoELECTRA fine-tuned 모델 추론 + 베이스라인 대비 비교 진단."""
import json
import os

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models", "koelectra")
MAX_LEN = 256

_tok = None
_model = None
_device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")


def _load():
    global _tok, _model
    if _model is None:
        _tok = AutoTokenizer.from_pretrained(MODEL_DIR)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).to(_device).eval()


def predict_proba(texts):
    _load()
    enc = _tok(texts, truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt").to(_device)
    with torch.no_grad():
        logits = _model(**enc).logits
    return torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()


def _fmt(turns):
    return " ".join(f"[{t['role'].split('_')[1].upper()}] {t['text']}" for t in turns)


if __name__ == "__main__":
    from sklearn.model_selection import train_test_split

    with open(os.path.join(BASE_DIR, "data", "PhishCatch-Data.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    labels = [c["label"] for c in cases]
    _, ev = train_test_split(cases, test_size=0.2, stratify=labels, random_state=42)

    texts = [_fmt(c["turns"]) for c in ev]
    probs = predict_proba(texts)

    # 오분류 케이스 추출
    fn = [(c["id"], p) for c, p in zip(ev, probs) if c["label"] == 1 and p < 0.5]
    fp = [(c["id"], p) for c, p in zip(ev, probs) if c["label"] == 0 and p >= 0.5]
    print(f"평가셋 {len(ev)}건")
    print(f"놓친 피싱(FN): {fn if fn else '없음'}")
    print(f"정상 오탐(FP): {[(i, f'{p*100:.0f}%') for i, p in fp] if fp else '없음'}")

    # 베이스라인이 놓쳤던 대출사기 3건이 이제 잡히는지
    print("\n[베이스라인 미탐 케이스 → KoELECTRA]")
    for cid in ["phishing_daechul_0153", "phishing_daechul_0174", "phishing_daechul_0177"]:
        c = next((c for c in ev if c["id"] == cid), None)
        if c:
            p = predict_proba([_fmt(c["turns"])])[0]
            print(f"  {cid}: {p*100:.0f}% {'✅ 탐지' if p >= 0.5 else '❌ 미탐'}")
