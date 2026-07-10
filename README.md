# KNU_AI_BOOT_Project_7조

## 주제: 보이스피싱 탐지 및 예방을 위한 AI 모델 개발

### 멤버

- 박준영
- 이재현
- 장지훈
- 최세민

## RAG 기반 보이스피싱 탐지 API

이 프로젝트는 정상/보이스피싱 학습 사례 JSON 파일을 SQLite DB에 저장한 뒤, 저장된 사례를 검색해 RAG 기반으로 위험도를 계산하고 생성형 모델 또는 템플릿으로 핵심근거를 생성합니다.

### 주요 기능

- 학습용 JSON 사례 파일 업로드 및 DB 저장
- DB 학습 사례 기반 유사 문장 검색
- 실시간 통화 로그, 통화 내용, 탐지 결과, 알림 이력 저장
- 보이스피싱 위험 패턴 탐지
- RAG 점수와 규칙 점수를 결합한 위험도 계산
- 생성형 모델 기반 핵심근거 생성
- LLM 설정이 없을 때 템플릿 핵심근거 자동 생성

### JSON 데이터 형식

```json
{
  "cases": [
    {
      "id": "phishing_call_001",
      "label": 1,
      "turns": [
        {
          "turn_index": 1,
          "role": "speaker_a",
          "text": "검찰입니다."
        },
        {
          "turn_index": 2,
          "role": "speaker_b",
          "text": "네?"
        }
      ]
    }
  ]
}
```

`label`은 보이스피싱이면 `1`, 정상이면 `0`입니다. `id`는 통화/세션 한 건을 구분하는 값이고, 한 통화 안의 발화는 `turns[].turn_index`로 구분합니다. `text` 필드를 직접 넣지 않아도 서버가 `turns`를 합쳐 RAG 검색용 텍스트를 자동 생성합니다.

### 실행 방법

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API 문서는 서버 실행 후 아래 주소에서 확인할 수 있습니다.

```text
http://127.0.0.1:8000/docs
```

### 샘플 데이터 업로드

```bash
curl -X POST "http://127.0.0.1:8000/training-cases/import-json" \
  -F "file=@samples/phishing_cases.json"
```

### 실시간 통화 음성 분석

클라이언트는 통화가 시작되면 먼저 `start` 메시지를 보내고, 백엔드는 이 시점에 `call_logs`에 통화 기록을 바로 생성합니다. 이후 클라이언트는 3~4초 단위의 mp3/wav 오디오 chunk를 WebSocket 바이너리 frame으로 전송합니다.

백엔드는 전달받은 오디오를 전사한 뒤 `call_messages`에 저장하고 누적 통화 내용을 KoELECTRA/RAG 기반으로 분석합니다. 분석 결과는 `detection_results`에 저장되며, 고위험 보이스피싱으로 판단되면 `notification_logs`에 알림 이력을 자동 저장하고 위험도와 핵심근거를 클라이언트로 반환합니다.

```text
ws://127.0.0.1:8000/ws/calls/analyze
```

통화 시작 메시지:

```json
{
  "type": "start",
  "device_id": 1,
  "name": "010-1234-5678",
  "audio_format": "wav"
}
```

`start` 메시지 없이 오디오 chunk를 먼저 보내면 백엔드는 통화 기록을 만들지 않고 에러를 반환합니다.

오디오 chunk 전송:

```text
<3~4초 wav 또는 mp3 binary frame>
```

정상으로 분석되면 서버는 `audio_analysis_ack` 응답을 반환합니다. 보이스피싱으로 판단되면 `audio_phishing_detected` 응답에 `risk_score`, `risk_level`, `matched_patterns`, `core_evidence`, `notification`을 포함해 반환합니다.

### 생성형 핵심근거 생성

`OPENAI_API_KEY`가 설정되어 있으면 `app/services/evidence_generator.py`에서 OpenAI 호환 SDK를 사용해 핵심근거를 생성합니다. 설정이 없거나 호출에 실패하면 템플릿 기반 핵심근거를 반환합니다.

OpenRouter 키를 사용할 경우 `.env`를 아래처럼 설정합니다.

```env
OPENAI_API_KEY=sk-or-v1...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openai/gpt-4o-mini
OPENROUTER_APP_TITLE=VoiceGuard AI
```
