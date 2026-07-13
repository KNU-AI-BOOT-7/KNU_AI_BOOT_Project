# GNU_AI_BOOT_Project 파일 구조 정리

> 주제: 보이스피싱 탐지 및 예방을 위한 AI 모델 개발 (KNU_AI_BOOT_Project_7조)
> 작성일: 2026-07-09 (현재 브랜치 `feat/koelectra-cascade` 기준)

## 1. 전체 아키텍처 요약

이 프로젝트는 두 개의 축으로 구성됩니다.

1. **모델 개발 축** (루트의 `.py` 스크립트들): 통화 전사 데이터를 모아 `data/PhishCatch-Data.json`으로 통합하고, 이를 이용해 베이스라인(TF-IDF)·KoELECTRA·LLM 순서로 점점 정교한 탐지 모델을 학습·평가합니다.
2. **서비스 축** (`app/` 폴더): FastAPI 기반 백엔드로, 학습 사례를 SQLite에 저장하고 RAG(검색+규칙 기반) 방식으로 실시간 통화를 분석해 위험도와 근거를 반환합니다.

두 축은 현재 독립적으로 존재합니다. `app/services/rag_detector.py`는 문자 n-gram 코사인 유사도 기반의 자체 RAG이고, 루트의 `realtime_detector.py`는 KoELECTRA → LLM 2단계 캐스케이드입니다. README에 따르면 `train_baseline.py`(TF-IDF)는 런타임에서는 제외되고 KoELECTRA의 성능 비교 대조군으로만 남아 있습니다.

## 2. 최상위 디렉터리 구조

```
GNU_AI_BOOT_Project/
├── app/                     # FastAPI 백엔드 (RAG 탐지 API)
├── data/                    # 원본/가공 데이터셋 + SQLite DB
├── models/                  # 학습된 모델 산출물 (baseline, koelectra)
├── tests/                   # 테스트용 케이스 샘플
├── 문서 정리/                # 프로젝트 문서 (보고서 등)
├── README.md                # 프로젝트 개요 + API 사용법
├── API_SPEC.md              # API 상세 명세
├── requirements.txt         # 서버(app/) 실행용 의존성
├── build_dataset.py         # 원본 데이터 → 통합 학습셋 변환
├── convert_nia_dataset.py   # NIA 금융상담 데이터 → 통합 JSON 변환 (보조 스크립트)
├── train_baseline.py        # TF-IDF + LogisticRegression 베이스라인 학습
├── train_transformer.py     # KoELECTRA fine-tuning
├── predict.py                # 베이스라인 모델 CLI 추론
├── predict_transformer.py    # KoELECTRA 모델 추론 함수
├── realtime_detector.py      # KoELECTRA → LLM 2단계 실시간 탐지 파이프라인
├── llm_judge.py               # LLM(OpenRouter) 기반 최종 판정 모듈
└── mp3_json.py                # 오디오(mp3/wav) → 화자분리+STT → dataset.json 변환
```

## 3. 모델 개발 파이프라인 (루트 스크립트)

### 3.1 데이터 준비

| 파일 | 역할 |
| --- | --- |
| `mp3_json.py` | 보이스피싱 녹취 mp3/wav를 whisper(STT, mlx-whisper/faster-whisper)로 전사하고 sherpa-onnx로 화자 분리한 뒤, `{call_id, label, phishing_type, segments}` 형태의 `dataset.json`으로 저장. 완전 로컬 실행(API 키 불필요), 중단 시 이어하기 지원. |
| `build_dataset.py` | `data/` 아래 4가지 원본(피싱 녹취 3종 + 정상 금융상담 + 정상 자유대화 + 직접 작성한 정상 아웃바운드 스크립트)을 읽어 하나의 통합 포맷 `data/PhishCatch-Data.json`으로 합침. 마스킹 토큰(O/X/*)과 STT 수집 아티팩트를 제거해 모델이 "지름길"로 학습하는 것을 방지. |
| `convert_nia_dataset.py` | (보조) NIA "금융분야 고객상담" 데이터셋(은행/보험/증권, 라벨 없음)을 동일한 `{cases:[{id,label,turns}]}` 포맷으로 변환. 이 폴더는 보이스피싱 라벨이 없어 전체 `label=0`(정상)으로 고정, `TX`/`RX` 접두사를 `speaker_a`/`speaker_b`로 매핑. 결과물은 `data/converted_dataset.json`. |

### 3.2 학습

| 파일 | 역할 |
| --- | --- |
| `train_baseline.py` | 문자 n-gram TF-IDF + LogisticRegression 베이스라인. `data/PhishCatch-Data.json`을 80/20 분할(seed 42)해 학습·평가하고 `models/baseline.joblib`으로 저장. 소스별 오분류, 판단 근거(가중치 상위 n-gram)까지 출력. KoELECTRA와의 성능 비교 대조군. |
| `train_transformer.py` | KoELECTRA(`monologg/koelectra-base-v3-discriminator`) fine-tuning. 화자 태그(`[A]`, `[B]`)를 붙여 문맥을 학습시키고, 클래스 불균형 대응을 위해 가중 손실(`WeightedTrainer`) 사용. 베이스라인과 동일 분할로 공정 비교. 결과는 `models/koelectra/`에 저장(체크포인트 포함). |

### 3.3 추론 / 실시간 탐지

| 파일 | 역할 |
| --- | --- |
| `predict.py` | 저장된 베이스라인 모델(`models/baseline.joblib`)로 CLI에서 문장 단위 판정 (대화형 또는 인자 전달). |
| `predict_transformer.py` | KoELECTRA 모델 로드 및 `predict_proba()` 제공. 단독 실행 시 평가셋에서 놓친 피싱(FN)/오탐(FP) 진단. |
| `llm_judge.py` | OpenRouter API(`OPENROUTER_API_KEY`, 기본 모델 `anthropic/claude-haiku-4.5`)로 통화 전사를 판정. 애매한 케이스의 최종 판정과 유형·근거·권장행동 생성 담당. |
| `realtime_detector.py` | **핵심 실시간 파이프라인.** 1차로 KoELECTRA가 매 발화 청크를 채점(누적 vs 최근 10턴 중 높은 값)하고, 점수가 게이트(0.30) 이상이면 2차로 LLM을 호출해 대화 흐름을 재판단. 최종 점수는 `max(KoELECTRA, LLM)`으로 결합(LLM은 점수를 낮출 수 없음, recall 우선 설계). 위험 등급: `warning`(0.70+), `danger`(0.85+). LLM 호출은 재판정 최소 간격(5턴)과 최소 문맥 길이(80자)로 비용을 억제. |

## 4. 서비스 백엔드 (`app/`)

FastAPI 기반 API 서버. 학습 사례를 SQLite에 저장하고, RAG(문자 n-gram 유사도 검색) + 규칙 기반 패턴 탐지를 결합해 위험도를 계산합니다. 위 3절의 KoELECTRA/LLM 파이프라인과는 별개의 자체 탐지 로직을 사용합니다.

| 파일 | 역할 |
| --- | --- |
| `app/main.py` | API 진입점. `GET /health`, `GET /calls`, `POST /training-cases/import-json`, `GET /training-cases`, `WS /ws/calls/analyze`(실시간 통화 분석 웹소켓) 엔드포인트 정의. |
| `app/database.py` | SQLite 연결 및 스키마 초기화(`training_cases`, `training_case_turns`, `call_logs`, `call_messages`, `detection_results`, `notification_logs` 테이블). DB 파일은 `data/voice_phishing.db`. |
| `app/repository.py` | DB CRUD 로직. 학습 사례 JSON 파싱/정규화(`parse_training_cases_json`), 통화 로그/발화/탐지결과/알림 저장 및 조회, 라벨 정규화(`_normalize_label`) 등. |
| `app/schemas.py` | Pydantic 요청/응답 스키마 정의 (`TrainingCase`, `CallLog`, `CallMessage`, `DetectionResult`, `NotificationLog` 등). |
| `app/services/rag_detector.py` | `RagPhishingDetector`: 규칙 기반 패턴 탐지(`RuleSignalDetector`, 정규식 기반 7개 카테고리) + 문자 n-gram 코사인 유사도 RAG 검색을 결합해 위험 점수 계산. 강한 피싱 패턴 조합 시 RAG 검색을 생략하는 최적화 포함. |
| `app/services/evidence_generator.py` | `EvidenceGenerator`: `OPENAI_API_KEY` 설정 시 OpenAI 호환 SDK(OpenRouter 포함)로 핵심근거 문장을 생성하고, 미설정/실패 시 템플릿 기반 근거로 폴백. |

### 4.1 API 흐름 요약

1. `POST /training-cases/import-json`으로 `{"cases":[{"id","label","turns":[...]}]}` 형식 JSON을 업로드 → SQLite에 저장.
2. 클라이언트가 `WS /ws/calls/analyze`에 연결 → `{"type":"start",...}`로 통화 시작(로그 생성) → `{"type":"message",...}`로 발화 전송.
3. 서버는 누적 통화 내용을 RAG로 분석 → `detection_results`에 저장 → 고위험(`risk_level=high`) 시 `notification_logs`에 알림 저장 후 클라이언트에 반환.

## 5. 데이터 폴더 (`data/`)

| 경로 | 내용 |
| --- | --- |
| `data/PhishCatch-Data.json` | `build_dataset.py`의 최종 산출물. 모델 학습에 사용하는 통합 데이터셋. |
| `data/converted_dataset.json` | `convert_nia_dataset.py`의 산출물 (NIA 금융상담 데이터, 전체 label=0). |
| `data/phishing/` | 보이스피싱 녹취 원본 3종(수사기관 사칭형/대출 사기형/바로 이 목소리) — `mp3_json.py` 결과물인 `results/dataset.json` 포함. |
| `data/normal/` | 정상 대화 원본 — 금융상담 데이터셋, 자유대화(AI-Hub 등), 직접 작성한 아웃바운드 권유 스크립트(하드 네거티브). |
| `data/voice_phishing.db` | (서버 실행 시 생성) SQLite DB. |

## 6. 모델 산출물 (`models/`)

| 경로 | 내용 |
| --- | --- |
| `models/baseline.joblib` | `train_baseline.py` 결과물 (TF-IDF + LogisticRegression 파이프라인). |
| `models/koelectra/` | `train_transformer.py` 결과물. `config.json`, `model.safetensors`, `tokenizer.json` 등 fine-tuned 모델 전체 + 학습 중간 체크포인트(`checkpoint-104/208/312`). |

## 7. 기타

- `tests/probe_cases.json`: 탐지 로직 점검용 샘플 케이스.
- `문서 정리/VoiceGuard_AI_진행보고서.docx`: 프로젝트 진행 보고서.
- `README.md` / `API_SPEC.md`: 각각 프로젝트 개요+실행법, API 상세 명세. 라벨 기준(0=정상, 1=피싱)과 위험도 기준(low<0.45, medium 0.45~0.75, high≥0.75)이 두 문서 모두에 정의됨.
