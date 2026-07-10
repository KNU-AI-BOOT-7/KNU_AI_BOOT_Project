"""프로젝트 공통 경로 설정.

런타임 패키지는 backend.app 아래에 두되, 데이터와 모델 산출물은 프로젝트 루트의
data/, models/를 사용하도록 한 곳에서 경로를 관리한다.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
APP_DIR = BACKEND_DIR / "app"

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"

DB_PATH = DATA_DIR / "voice_phishing.db"
TRAINING_DATA_PATH = DATA_DIR / "PhishCatch-Data.json"
BASELINE_MODEL_PATH = MODELS_DIR / "baseline.joblib"
KOELECTRA_MODEL_DIR = MODELS_DIR / "koelectra"
ENV_PATH = PROJECT_ROOT / ".env"
