# KNU_AI_BOOT_Project_7조

## 주제: 보이스피싱 탐지 및 예방을 위한 AI 모델 개발

### 멤버

- 박준영
- 이재현
- 장지훈
- 최세민

## RAG 기반 보이스피싱 탐지 API

이 프로젝트는 보이스피싱 사례 JSON 파일을 SQLite DB에 저장한 뒤, 저장된 사례를 검색해 RAG 기반으로 위험도를 계산하고 생성형 모델 또는 템플릿으로 탐지 근거를 생성합니다.

### 주요 기능

- JSON 사례 파일 업로드 및 DB 저장
- DB 사례 기반 유사 문장 검색
- 보이스피싱 위험 패턴 탐지
- RAG 점수와 규칙 점수를 결합한 위험도 계산
- 생성형 모델 기반 근거 생성
- LLM 설정이 없을 때 템플릿 근거 자동 생성

### JSON 데이터 형식

```json
{
  "cases": [
    {
      "text": "검찰입니다. 고객님 계좌가 범죄에 연루되어 안전계좌로 이체해야 합니다.",
      "label": 1,
      "reason": "수사기관 사칭, 범죄 연루 압박, 안전계좌 이체 요구",
      "source": "sample"
    }
  ]
}
```

`label`은 보이스피싱이면 `1`, 정상이면 `0`입니다.

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
curl -X POST "http://127.0.0.1:8000/cases/import-json" \
  -F "file=@samples/phishing_cases.json"
```

### RAG 탐지 요청

```bash
curl -X POST "http://127.0.0.1:8000/detect/rag" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "검찰입니다. 계좌가 범죄에 연루되어 안전계좌로 이체해야 합니다.",
    "top_k": 5
  }'
```

### 생성형 근거 생성

`OPENAI_API_KEY`가 설정되어 있으면 `app/services/evidence_generator.py`에서 OpenAI SDK를 사용해 근거를 생성합니다. 설정이 없거나 호출에 실패하면 템플릿 기반 근거를 반환합니다.
