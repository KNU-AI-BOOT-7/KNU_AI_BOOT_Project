# API 명세

## 기본 주소

```text
HTTP: http://127.0.0.1:8000
WS: ws://127.0.0.1:8000
```

## 1. 상태 확인

```http
GET /health
```

응답:

```json
{
  "status": "ok"
}
```

## 2. 학습 데이터 업로드

```http
POST /training-cases/import-json
```

요청:

```bash
curl -X POST "http://127.0.0.1:8000/training-cases/import-json" \
  -F "file=@samples/phishing_cases.json"
```

JSON 형식:

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
        }
      ]
    }
  ]
}
```

응답:

```json
{
  "inserted_count": 5,
  "skipped_count": 0
}
```

## 3. 학습 데이터 조회

```http
GET /training-cases
```

## 4. 통화 기록 목록 조회

```http
GET /calls
```

요청:

```bash
curl "http://127.0.0.1:8000/calls?limit=20"
```

응답:

```json
{
  "risk_level_counts": {
    "low": 7,
    "medium": 3,
    "high": 2
  },
  "calls": [
    {
      "id": 10,
      "called_at": "2026-07-09 10:20:31",
      "risk_score": 0.84,
      "risk_level": "high",
      "phishing_type": "기관 사칭",
      "file_type": "realtime"
    },
    {
      "id": 9,
      "called_at": "2026-07-09 09:18:02",
      "risk_score": 0.12,
      "risk_level": "low",
      "phishing_type": "정상",
      "file_type": "recording"
    }
  ]
}
```

응답 필드:

| 필드 | 설명 |
| --- | --- |
| `risk_level_counts` | 전체 통화 기록의 리스크 레벨별 개수 |
| `calls` | 통화 기록 목록 |
| `id` | 통화 로그 ID |
| `called_at` | 통화 기록 생성 일시 |
| `risk_score` | 0~1 사이 위험도 수치 |
| `risk_level` | `low`, `medium`, `high` |
| `phishing_type` | 대표 피싱 유형. 정상 통화면 `정상` |
| `file_type` | `realtime` 또는 `recording` |

## 5. 통화 기록 상세 조회

```http
GET /calls/{log_id}
```

요청:

```bash
curl "http://127.0.0.1:8000/calls/10"
```

응답:

```json
{
  "id": 10,
  "phishing_type": "기관 사칭",
  "matched_patterns": ["수사기관/공공기관 사칭", "범죄 연루 압박"],
  "core_evidence": "검찰 사칭 표현과 계좌 범죄 연루 표현이 탐지되었습니다."
}
```

## 6. 실시간 통화 분석

```text
WS /ws/calls/analyze
```

통화 시작 요청:

```json
{
  "type": "start",
  "device_id": 1,
  "name": "테스트 통화",
  "file_type": "realtime"
}
```

통화 시작 응답:

```json
{
  "type": "call_started",
  "call": {
    "id": 1,
    "device_id": 1,
    "name": "테스트 통화",
    "file_type": "realtime",
    "status": "normal",
    "risk_score": 0.0,
    "risk_level": "low",
    "detected_label": 0,
    "phishing_type": "",
    "core_evidence": "",
    "created_at": "2026-07-09 10:20:31",
    "updated_at": "2026-07-09 10:20:31"
  }
}
```

발화 분석 요청:

```json
{
  "type": "message",
  "role": "speaker_a",
  "content": "검찰입니다. 계좌가 범죄에 연루되었습니다.",
  "turn_index": 1
}
```

정상 응답:

```json
{
  "type": "analysis_ack",
  "log_id": 1,
  "message_id": 12,
  "is_phishing": false,
  "risk_score": 0.2,
  "risk_level": "low",
  "phishing_type": ""
}
```

피싱 탐지 응답:

```json
{
  "type": "phishing_detected",
  "log_id": 1,
  "message_id": 13,
  "is_phishing": true,
  "risk_score": 0.84,
  "risk_level": "high",
  "phishing_type": "기관 사칭",
  "matched_patterns": ["수사기관/공공기관 사칭"],
  "core_evidence": "검찰 사칭 표현이 탐지되었습니다.",
  "notification": {
    "id": 3,
    "message": "보이스피싱 위험이 높게 탐지되었습니다. 통화를 종료하고 공식 대표번호로 확인하세요.",
    "status": "sent",
    "created_at": "2026-07-09 10:21:03"
  }
}
```

실시간 분석 응답에는 RAG 유사 사례 원문(`retrieved_cases`)을 포함하지 않습니다.
유사 사례는 백엔드 내부 근거 생성에만 사용하고, 클라이언트에는 위험도와 핵심근거만 반환합니다.

에러 응답:

```json
{
  "type": "error",
  "message": "통화 발화를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다."
}
```

## 라벨 기준

```text
0: 정상
1: 보이스피싱
```

## 위험도 기준

```text
low: risk_score < 0.45
medium: 0.45 <= risk_score < 0.75
high: risk_score >= 0.75
```
