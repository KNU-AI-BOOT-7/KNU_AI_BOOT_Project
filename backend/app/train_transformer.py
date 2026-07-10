"""2차 탐지 후보: 한국어 사전학습 언어모델(KoELECTRA) fine-tuning.

TF-IDF 베이스라인의 문맥 이해 한계(대출사기 vs 정상 대출상담의 어휘 근접성)를
문맥 이해형 모델로 넘어설 수 있는지 검증한다. 베이스라인과 동일한 80/20 분할(seed 42)로
공정 비교하며, Accuracy/Precision/Recall/F1을 함께 출력한다.

실행:
    .venv/bin/python -m app.train_transformer                    # 기본 KoELECTRA
    MODEL=klue/bert-base .venv/bin/python -m app.train_transformer

FP16: CUDA에서만 활성화한다. MPS(Apple Silicon)는 fp16 mixed precision 학습이
불안정하므로 자동으로 끈다 (추론 속도에는 영향 없음).
"""
import json
import os
import re

import numpy as np
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.model_selection import train_test_split
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "PhishCatch-Data.json")
MODEL_NAME = os.environ.get("MODEL", "monologg/koelectra-base-v3-discriminator")
OUT_DIR = os.path.join(BASE_DIR, "models", "koelectra")
MAX_LEN = 256          # 피싱 신호는 통화 초중반에 몰려 있어 256으로 절단해도 대부분 포착
SEED = 42
EPOCHS = 3


def load_split():
    with open(DATA_PATH, encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    texts, labels = [], []
    for c in cases:
        # 화자 구분을 모델이 볼 수 있게 태그를 붙인다
        text = " ".join(f"[{t['role'].split('_')[1].upper()}] {t['text']}" for t in c["turns"])
        texts.append(text)
        labels.append(c["label"])
    return train_test_split(texts, labels, test_size=0.2, stratify=labels, random_state=SEED)


class WeightedTrainer(Trainer):
    """클래스 불균형(피싱 소수) 대응: 피싱 오분류에 더 큰 손실 가중치."""

    def __init__(self, class_weights, **kwargs):
        super().__init__(**kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss_fct = torch.nn.CrossEntropyLoss(
            weight=self.class_weights.to(outputs.logits.device)
        )
        loss = loss_fct(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss


def compute_metrics(pred):
    labels = pred.label_ids
    preds = pred.predictions.argmax(-1)
    acc = accuracy_score(labels, preds)
    # 피싱(1) 클래스 기준 지표
    p, r, f1, _ = precision_recall_fscore_support(
        labels, preds, labels=[1], average="binary", zero_division=0
    )
    return {"accuracy": acc, "precision": p, "recall": r, "f1": f1}


class DS(torch.utils.data.Dataset):
    def __init__(self, enc, labels):
        self.enc = enc
        self.labels = labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: v[i] for k, v in self.enc.items()}
        item["labels"] = torch.tensor(self.labels[i])
        return item


def main():
    torch.manual_seed(SEED)
    X_tr, X_te, y_tr, y_te = load_split()
    print(f"모델: {MODEL_NAME}")
    print(f"학습 {len(X_tr)}건 / 평가 {len(X_te)}건 (평가셋 피싱 {sum(y_te)}건)")

    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    use_fp16 = torch.cuda.is_available()  # MPS/CPU에서는 fp16 끔
    print(f"디바이스: {device} / fp16: {use_fp16}\n")

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    enc_tr = tok(X_tr, truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt")
    enc_te = tok(X_te, truncation=True, padding=True, max_length=MAX_LEN, return_tensors="pt")

    # class_weight='balanced'와 동일한 계산
    n = len(y_tr)
    w0 = n / (2 * (n - sum(y_tr)))
    w1 = n / (2 * sum(y_tr))
    class_weights = torch.tensor([w0, w1], dtype=torch.float)

    model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME, num_labels=2)

    args = TrainingArguments(
        output_dir=OUT_DIR,
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        learning_rate=2e-5,
        warmup_ratio=0.1,
        weight_decay=0.01,
        fp16=use_fp16,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        logging_steps=20,
        report_to="none",
        seed=SEED,
    )

    trainer = WeightedTrainer(
        class_weights=class_weights,
        model=model,
        args=args,
        train_dataset=DS(enc_tr, y_tr),
        eval_dataset=DS(enc_te, y_te),
        compute_metrics=compute_metrics,
    )
    trainer.train()

    print("\n=== 최종 평가 (best model) ===")
    metrics = trainer.evaluate()
    for k in ["eval_accuracy", "eval_precision", "eval_recall", "eval_f1"]:
        print(f"  {k.replace('eval_', ''):10} {metrics[k] * 100:.2f}%")

    trainer.save_model(OUT_DIR)
    tok.save_pretrained(OUT_DIR)
    print(f"\n모델 저장: {OUT_DIR}")


if __name__ == "__main__":
    main()
