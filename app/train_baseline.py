"""베이스라인: TF-IDF(문자 n-gram) + Logistic Regression 피싱 분류기.

data/PhishCatch-Data.json을 80/20으로 나눠 학습·평가하고,
소스별 오분류와 판단 근거(상위 가중치 n-gram)를 출력한다.
모델은 models/baseline.joblib으로 저장.
"""
import json
import os
import re

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "PhishCatch-Data.json")
MODEL_PATH = os.path.join(BASE_DIR, "models", "baseline.joblib")
SEED = 42


def normalize(text):
    """구두점 제거: 소스별 전사 스타일(마침표 유무 등)을 지름길로 학습하는 것을 방지."""
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_cases():
    with open(DATA_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    texts, labels, sources = [], [], []
    for c in cases:
        texts.append(normalize(" ".join(t["text"] for t in c["turns"])))
        labels.append(c["label"])
        sources.append(re.sub(r"_\d+$", "", c["id"]))  # phishing_susagigwan_0001 → phishing_susagigwan
    return texts, np.array(labels), np.array(sources)


def main():
    texts, labels, sources = load_cases()
    X_tr, X_te, y_tr, y_te, src_tr, src_te = train_test_split(
        texts, labels, sources, test_size=0.2, stratify=labels, random_state=SEED
    )
    print(f"학습 {len(X_tr)}건 / 평가 {len(X_te)}건 (평가셋 피싱 {y_te.sum()}건)\n")

    model = Pipeline([
        ("tfidf", TfidfVectorizer(
            analyzer="char_wb", ngram_range=(2, 4),
            min_df=2, max_features=200_000, sublinear_tf=True,
        )),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000)),
    ])
    model.fit(X_tr, y_tr)
    y_pred = model.predict(X_te)

    print(classification_report(y_te, y_pred, target_names=["정상(0)", "피싱(1)"], digits=4))
    tn, fp, fn, tp = confusion_matrix(y_te, y_pred).ravel()
    print(f"혼동행렬: 피싱 적중 {tp} / 피싱 놓침 {fn} / 정상 오인(→피싱) {fp} / 정상 적중 {tn}\n")

    print("소스별 평가셋 성적:")
    for src in sorted(set(src_te)):
        m = src_te == src
        correct = (y_pred[m] == y_te[m]).sum()
        print(f"  {src:<25} {correct}/{m.sum()} 정답")
    wrong = [(s, t, p) for s, t, p in zip(src_te, y_te, y_pred) if t != p]
    if wrong:
        print(f"\n오분류 {len(wrong)}건: {[(s, f'{t}→{p}') for s, t, p in wrong]}")

    # 판단 근거: 가중치 상위 n-gram
    vocab = np.array(model["tfidf"].get_feature_names_out())
    coef = model["clf"].coef_[0]
    top = np.argsort(coef)
    print("\n피싱 쪽 증거 상위 15개 :", ", ".join(repr(w) for w in vocab[top[-15:]][::-1]))
    print("정상 쪽 증거 상위 15개 :", ", ".join(repr(w) for w in vocab[top[:15]]))

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"\n모델 저장: {MODEL_PATH}")


if __name__ == "__main__":
    main()
