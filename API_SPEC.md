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
  -F "file=@data/PhishCatch-Data.json"
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

## 6. 통화 대화 내역 조회

```http
GET /calls/{log_id}/messages
```

요청:

```bash
curl "http://127.0.0.1:8000/calls/10/messages"
```

응답:

```json
{
  "log_id": 10,
  "messages": [
    {
      "id": 21,
      "log_id": 10,
      "turn_index": 1,
      "content": "안녕하세요. 카드 결제일 문의드립니다.",
      "created_at": "2026-07-09 10:20:35"
    }
  ]
}
```

## 7. 녹음 파일 분석

```http
POST /calls/analyze-audio
```

요청:

```bash
curl -X POST "http://127.0.0.1:8000/calls/analyze-audio?device_id=1" \
  -F "file=@call.m4a"
```

응답:

```json
{
  "type": "audio_analysis",
  "log_id": 11,
  "file_name": "call.m4a",
  "segments": [
    {
      "chunk_id": 1,
      "start_time": 0.0,
      "end_time": 3.2,
      "text": "서울중앙지검입니다."
    }
  ],
  "is_phishing": true,
  "risk_score": 0.91,
  "risk_level": "high",
  "phishing_type": "기관 사칭",
  "matched_patterns": ["수사기관/공공기관 사칭"],
  "core_evidence": "수사기관 사칭 표현이 탐지되었습니다.",
  "notification": null
}
```

녹음 파일 분석은 `mp3`, `wav`, `m4a` 업로드를 지원합니다. `m4a`는 서버에서 임시 `wav`로 변환한 뒤 `backend.app.mp3_json` 전사 모듈에 전달합니다.

## 8. 실시간 통화 분석

```text
WS /ws/calls/analyze
```

위험도 점수는 KoELECTRA 모델이 준비되어 있으면 KoELECTRA가 계산하고,
RAG와 규칙 패턴은 주요 키워드와 근거 생성을 보조합니다.
KoELECTRA 모델이 없으면 RAG 기반 위험도로 대체합니다.

통화 시작 요청:

```json
{
  "type": "start",
  "device_id": 1,
  "name": "테스트 통화",
  "file_type": "realtime",
  "audio_format": "m4a"
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
  },
  "audio_format": "m4a"
}
```

오디오 chunk 요청:

`start` 이후 프론트는 3~4초 단위의 mp3, wav 또는 m4a 바이너리 frame을 그대로 전송합니다.
백엔드는 전사 결과를 화자 구분 없이 순서와 발화 내용으로 저장합니다.

```text
<3~4초 wav, mp3 또는 m4a binary frame>
```

테스트 도구에서 바이너리 frame 전송이 어려우면 base64 JSON 방식도 사용할 수 있습니다.

```json
{
  "type": "audio_chunk",
  "chunk_index": 1,
  "audio_format": "m4a",
  "audio_base64": "AAAA..."
}
```

정상 응답:

```json
{
  "type": "audio_analysis_ack",
  "log_id": 1,
  "chunk_index": 1,
  "message_ids": [12],
  "converted_text": "안녕하세요. 카드 결제일 문의드립니다.",
  "transcripts": [
    {
      "message_id": 12,
      "turn_index": 1,
      "content": "안녕하세요. 카드 결제일 문의드립니다.",
      "converted_text": "안녕하세요. 카드 결제일 문의드립니다.",
      "start_time": 0.0,
      "end_time": 3.1
    }
  ],
  "is_phishing": false,
  "risk_score": 0.2,
  "risk_level": "low",
  "phishing_type": "정상"
}
```

피싱 탐지 응답:

```json
{
  "type": "audio_phishing_detected",
  "log_id": 1,
  "chunk_index": 3,
  "message_ids": [13],
  "converted_text": "서울중앙지검입니다. 계좌가 범죄에 연루되었습니다.",
  "transcripts": [
    {
      "message_id": 13,
      "turn_index": 3,
      "content": "서울중앙지검입니다. 계좌가 범죄에 연루되었습니다.",
      "converted_text": "서울중앙지검입니다. 계좌가 범죄에 연루되었습니다.",
      "start_time": 0.0,
      "end_time": 3.8
    }
  ],
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

전사 실패 응답:

```json
{
  "type": "audio_chunk_error",
  "log_id": 1,
  "chunk_index": 1,
  "message": "오디오 chunk 전사에 실패했습니다: 전사 모듈 또는 오디오 파일을 확인하세요."
}
```

에러 응답:

```json
{
  "type": "error",
  "message": "오디오 chunk를 보내기 전에 먼저 start 메시지로 통화 기록을 생성해야 합니다."
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
