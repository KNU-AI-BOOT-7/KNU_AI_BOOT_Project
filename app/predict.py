"""저장된 베이스라인 모델로 직접 테스트.

사용법:
  .venv/bin/python -m app.predict                    # 대화형 모드 (문장 입력 → 판정)
  .venv/bin/python -m app.predict "검찰청입니다..."   # 한 번만 판정
"""
import os
import sys

import joblib

from app.train_baseline import normalize

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "baseline.joblib")


def predict(model, text):
    prob = model.predict_proba([normalize(text)])[0][1]
    verdict = "🚨 피싱" if prob >= 0.5 else "✅ 정상"
    return f"{verdict}  (피싱 확률 {prob * 100:.1f}%)"


def main():
    model = joblib.load(MODEL_PATH)
    if len(sys.argv) > 1:
        print(predict(model, " ".join(sys.argv[1:])))
        return
    print("통화 내용을 입력하세요 (종료: 빈 줄 입력 또는 Ctrl+C)\n")
    while True:
        try:
            text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            break
        print(predict(model, text), "\n")


if __name__ == "__main__":
    main()
