# Voice Phishing Detection ERD

```mermaid
erDiagram
    training_cases ||--o{ training_case_turns : "has"
    call_logs ||--o{ call_messages : "has"
    call_logs ||--o{ detection_results : "has"
    call_logs ||--o{ notification_logs : "has"

    training_cases {
        INTEGER id PK
        TEXT external_id
        TEXT text
        INTEGER label
        TEXT source
        TEXT created_at
    }

    training_case_turns {
        INTEGER id PK
        INTEGER case_id FK
        INTEGER turn_index
        TEXT text
        TEXT created_at
    }

    call_logs {
        INTEGER id PK
        INTEGER device_id
        TEXT name
        TEXT file_type
        TEXT status
        REAL risk_score
        TEXT risk_level
        INTEGER detected_label
        TEXT phishing_type
        TEXT core_evidence
        TEXT created_at
        TEXT updated_at
    }

    call_messages {
        INTEGER id PK
        INTEGER log_id FK
        INTEGER turn_index
        TEXT content
        TEXT created_at
    }

    detection_results {
        INTEGER id PK
        INTEGER log_id FK
        REAL risk_score
        TEXT risk_level
        INTEGER detected_label
        TEXT core_evidence
        TEXT matched_patterns
        TEXT retrieved_case_ids
        TEXT model_version
        TEXT created_at
    }

    notification_logs {
        INTEGER id PK
        INTEGER log_id FK
        TEXT reason
        TEXT message
        TEXT status
        TEXT created_at
    }
```

## Relationships

- `training_cases.id` -> `training_case_turns.case_id`
- `call_logs.id` -> `call_messages.log_id`
- `call_logs.id` -> `detection_results.log_id`
- `call_logs.id` -> `notification_logs.log_id`

All child rows are configured with `ON DELETE CASCADE`.

## Notes

- Speaker fields were removed from `training_case_turns` and `call_messages`.
- `call_messages.content` stores the converted/transcribed sentence.
- `detection_results.matched_patterns` and `detection_results.retrieved_case_ids` are stored as JSON strings.
- `call_logs` stores the latest summarized detection state, while `detection_results` stores detection history.
