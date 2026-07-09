"""학습 데이터, 통화 로그, 탐지 결과를 다루는 저장소 계층."""

from __future__ import annotations

import json
from typing import Any

from app.database import get_connection
from app.schemas import (
    CallLog,
    CallLogCreate,
    CallMessage,
    CallMessageCreate,
    DetectionResult,
    NotificationCreate,
    NotificationLog,
    TrainingCase,
    TrainingCaseCreate,
    TrainingCaseTurn,
    TrainingCaseTurnCreate,
)


def insert_training_case(case: TrainingCaseCreate) -> int:
    """학습 사례 1건을 저장하고 DB id를 반환한다."""
    case = _normalize_training_case_text(case)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO training_cases(external_id, text, label, source)
            VALUES (?, ?, ?, ?)
            """,
            (case.external_id.strip(), case.text.strip(), case.label, case.source.strip()),
        )
        case_id = int(cursor.lastrowid)
        _insert_training_case_turns(connection, case_id, case.turns)
        return case_id


def get_training_case(case_id: int) -> TrainingCase:
    """id로 학습 사례 1건을 조회한다."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, external_id, text, label, source, created_at
            FROM training_cases
            WHERE id = ?
            """,
            (case_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"case_id={case_id} 학습 사례를 찾을 수 없습니다.")

    data = dict(row)
    data["turns"] = list_training_case_turns(case_id)
    return TrainingCase(**data)


def insert_training_cases(cases: list[TrainingCaseCreate]) -> int:
    """여러 학습 사례를 하나의 트랜잭션으로 저장한다."""
    if not cases:
        return 0

    inserted_count = 0
    with get_connection() as connection:
        for case in cases:
            case = _normalize_training_case_text(case)
            cursor = connection.execute(
                """
                INSERT INTO training_cases(external_id, text, label, source)
                VALUES (?, ?, ?, ?)
                """,
                (case.external_id.strip(), case.text.strip(), case.label, case.source.strip()),
            )
            case_id = int(cursor.lastrowid)
            _insert_training_case_turns(connection, case_id, case.turns)
            inserted_count += 1

    return inserted_count


def list_training_cases(limit: int = 100) -> list[TrainingCase]:
    """최근 저장된 학습 사례를 조회한다."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, external_id, text, label, source, created_at
            FROM training_cases
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_build_training_case(dict(row)) for row in rows]


def list_all_training_cases() -> list[TrainingCase]:
    """RAG 검색에 사용할 모든 학습 사례를 조회한다."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, external_id, text, label, source, created_at
            FROM training_cases
            ORDER BY id ASC
            """
        ).fetchall()

    return [_build_training_case(dict(row)) for row in rows]


def list_training_case_turns(case_id: int) -> list[TrainingCaseTurn]:
    """학습 사례에 속한 발화를 순서대로 조회한다."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, case_id, turn_index, role, text, created_at
            FROM training_case_turns
            WHERE case_id = ?
            ORDER BY turn_index ASC, id ASC
            """,
            (case_id,),
        ).fetchall()

    return [TrainingCaseTurn(**dict(row)) for row in rows]


def parse_training_cases_json(raw_bytes: bytes) -> tuple[list[TrainingCaseCreate], int]:
    """
    업로드된 학습용 JSON을 정규화한다.

    권장 형식:
    [
      {
        "id": "normal_S0001",
        "label": 0,
        "source": "financial_consulting",
        "text": "speaker_a: ... speaker_b: ...",
        "turns": [{"turn_index": 1, "role": "speaker_a", "text": "..."}]
      }
    ]
    """
    payload: Any = json.loads(raw_bytes.decode("utf-8-sig"))
    items = payload.get("cases", payload) if isinstance(payload, dict) else payload

    if not isinstance(items, list):
        raise ValueError("JSON은 리스트이거나 {'cases': [...]} 형식이어야 합니다.")

    cases: list[TrainingCaseCreate] = []
    skipped_count = 0

    for item in items:
        if not isinstance(item, dict):
            skipped_count += 1
            continue

        try:
            turns = _parse_training_turns(item.get("turns", []))
            text = str(item.get("text", item.get("content", ""))).strip()
            if not text and turns:
                text = _build_training_text_from_turns(turns)
            if not text:
                raise ValueError("text 또는 turns가 필요합니다.")

            raw_label = item.get("label", item.get("is_phishing"))
            label = _normalize_label(raw_label)
            case = TrainingCaseCreate(
                external_id=str(item.get("external_id", item.get("id", ""))),
                text=text,
                label=label,
                source=str(item.get("source", "")),
                turns=turns,
            )
        except Exception:
            skipped_count += 1
            continue

        cases.append(case)

    return cases, skipped_count


def _build_training_case(row: dict) -> TrainingCase:
    """학습 사례 row에 발화 목록을 붙여 스키마 객체로 만든다."""
    row["turns"] = list_training_case_turns(int(row["id"]))
    return TrainingCase(**row)


def _normalize_training_case_text(case: TrainingCaseCreate) -> TrainingCaseCreate:
    """text가 비어 있으면 turns를 합쳐 학습/RAG용 text를 만든다."""
    text = case.text.strip()
    if not text and case.turns:
        text = _build_training_text_from_turns(case.turns)

    if not text:
        raise ValueError("학습 사례에는 text 또는 turns가 필요합니다.")

    return TrainingCaseCreate(
        external_id=case.external_id,
        text=text,
        label=case.label,
        source=case.source,
        turns=case.turns,
    )


def _insert_training_case_turns(
    connection,
    case_id: int,
    turns: list[TrainingCaseTurnCreate],
) -> None:
    """학습 사례 발화 목록을 저장한다."""
    if not turns:
        return

    connection.executemany(
        """
        INSERT INTO training_case_turns(case_id, turn_index, role, text)
        VALUES (?, ?, ?, ?)
        """,
        [
            (case_id, turn.turn_index, turn.role.strip(), turn.text.strip())
            for turn in turns
        ],
    )


def _parse_training_turns(raw_turns: Any) -> list[TrainingCaseTurnCreate]:
    """JSON의 turns 값을 학습 사례 발화 스키마로 변환한다."""
    if raw_turns in (None, ""):
        return []

    if not isinstance(raw_turns, list):
        raise ValueError("turns는 리스트여야 합니다.")

    turns: list[TrainingCaseTurnCreate] = []
    for index, item in enumerate(raw_turns, start=1):
        if not isinstance(item, dict):
            raise ValueError("turns 항목은 객체여야 합니다.")

        turn_index = item.get("turn_index", item.get("turn", index))
        text = str(item.get("text", item.get("content", ""))).strip()
        role = str(item.get("role", item.get("speaker", "unknown"))).strip()
        turns.append(
            TrainingCaseTurnCreate(
                turn_index=int(turn_index),
                role=role or "unknown",
                text=text,
            )
        )

    return turns


def _build_training_text_from_turns(turns: list[TrainingCaseTurnCreate]) -> str:
    """turns만 있는 JSON을 RAG 검색용 text로 합친다."""
    return "\n".join(f"{turn.role}: {turn.text}" for turn in turns)


def create_call_log(call: CallLogCreate) -> CallLog:
    """실시간 분석 대상 통화 로그를 생성한다."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO call_logs(device_id, name)
            VALUES (?, ?)
            """,
            (call.device_id, call.name.strip()),
        )
        log_id = int(cursor.lastrowid)

    return get_call_log(log_id)


def get_call_log(log_id: int) -> CallLog:
    """id로 통화 로그를 조회한다."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, device_id, name, status, risk_score, risk_level,
                   detected_label, phishing_type, core_evidence, created_at, updated_at
            FROM call_logs
            WHERE id = ?
            """,
            (log_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"log_id={log_id} 통화 로그를 찾을 수 없습니다.")

    return CallLog(**dict(row))


def list_call_logs(limit: int = 100) -> list[CallLog]:
    """최근 통화 로그를 조회한다."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, device_id, name, status, risk_score, risk_level,
                   detected_label, phishing_type, core_evidence, created_at, updated_at
            FROM call_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [CallLog(**dict(row)) for row in rows]


def insert_call_message(log_id: int, message: CallMessageCreate) -> CallMessage:
    """통화 발화 1건을 저장한다."""
    turn_index = message.turn_index or (count_call_messages(log_id) + 1)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO call_messages(log_id, turn_index, role, content)
            VALUES (?, ?, ?, ?)
            """,
            (log_id, turn_index, message.role.strip(), message.content.strip()),
        )
        message_id = int(cursor.lastrowid)

    return get_call_message(message_id)


def get_call_message(message_id: int) -> CallMessage:
    """id로 통화 발화 1건을 조회한다."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, log_id, turn_index, role, content, created_at
            FROM call_messages
            WHERE id = ?
            """,
            (message_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"message_id={message_id} 발화를 찾을 수 없습니다.")

    return CallMessage(**dict(row))


def list_call_messages(log_id: int) -> list[CallMessage]:
    """통화 로그에 속한 모든 발화를 순서대로 조회한다."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, log_id, turn_index, role, content, created_at
            FROM call_messages
            WHERE log_id = ?
            ORDER BY turn_index ASC, id ASC
            """,
            (log_id,),
        ).fetchall()

    return [CallMessage(**dict(row)) for row in rows]


def count_call_messages(log_id: int) -> int:
    """통화 로그에 저장된 발화 개수를 계산한다."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM call_messages WHERE log_id = ?",
            (log_id,),
        ).fetchone()

    return int(row["count"])


def build_call_text(log_id: int) -> str:
    """저장된 통화 발화를 하나의 탐지용 텍스트로 합친다."""
    messages = list_call_messages(log_id)
    return "\n".join(f"{message.role}: {message.content}" for message in messages)


def save_detection_result(
    log_id: int,
    risk_score: float,
    risk_level: str,
    detected_label: int,
    core_evidence: str,
    matched_patterns: list[str],
    retrieved_case_ids: list[int],
    model_version: str = "rag-v1",
) -> DetectionResult:
    """탐지 결과를 저장하고 통화 로그의 최신 상태를 갱신한다."""
    status = "phishing" if detected_label == 1 else "normal"
    phishing_type = _infer_phishing_type(matched_patterns, detected_label)
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO detection_results(
                log_id, risk_score, risk_level, detected_label, core_evidence,
                matched_patterns, retrieved_case_ids, model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                risk_score,
                risk_level,
                detected_label,
                core_evidence,
                json.dumps(matched_patterns, ensure_ascii=False),
                json.dumps(retrieved_case_ids, ensure_ascii=False),
                model_version,
            ),
        )
        result_id = int(cursor.lastrowid)
        connection.execute(
            """
            UPDATE call_logs
            SET status = ?,
                risk_score = ?,
                risk_level = ?,
                detected_label = ?,
                phishing_type = ?,
                core_evidence = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                risk_score,
                risk_level,
                detected_label,
                phishing_type,
                core_evidence,
                log_id,
            ),
        )

    return get_detection_result(result_id)


def get_detection_result(result_id: int) -> DetectionResult:
    """id로 탐지 결과를 조회한다."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, log_id, risk_score, risk_level, detected_label, core_evidence,
                   matched_patterns, retrieved_case_ids, model_version, created_at
            FROM detection_results
            WHERE id = ?
            """,
            (result_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"result_id={result_id} 탐지 결과를 찾을 수 없습니다.")

    data = dict(row)
    data["matched_patterns"] = json.loads(data["matched_patterns"] or "[]")
    data["retrieved_case_ids"] = json.loads(data["retrieved_case_ids"] or "[]")
    return DetectionResult(**data)


def _infer_phishing_type(matched_patterns: list[str], detected_label: int) -> str:
    """탐지 패턴 목록에서 클라이언트에 보여줄 대표 피싱 유형을 고른다."""
    if detected_label != 1:
        return ""

    type_priority = [
        ("수사기관/공공기관 사칭", "기관 사칭"),
        ("범죄 연루 압박", "수사기관 사칭"),
        ("금전 이체 유도", "금전 이체 유도"),
        ("개인정보/인증 요구", "개인정보/인증 요구"),
        ("앱 설치/원격제어 유도", "앱 설치/원격제어 유도"),
        ("긴급성/비밀 유지 압박", "긴급성/비밀 유지 압박"),
    ]
    for pattern, phishing_type in type_priority:
        if pattern in matched_patterns:
            return phishing_type

    return "보이스피싱 의심"


def insert_notification(log_id: int, notification: NotificationCreate) -> NotificationLog:
    """알림 발송 이력을 저장한다."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO notification_logs(log_id, reason, message, status)
            VALUES (?, ?, ?, ?)
            """,
            (
                log_id,
                notification.reason.strip(),
                notification.message.strip(),
                notification.status.strip(),
            ),
        )
        notification_id = int(cursor.lastrowid)

    return get_notification(notification_id)


def get_notification(notification_id: int) -> NotificationLog:
    """id로 알림 이력을 조회한다."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, log_id, reason, message, status, created_at
            FROM notification_logs
            WHERE id = ?
            """,
            (notification_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"notification_id={notification_id} 알림 이력을 찾을 수 없습니다.")

    return NotificationLog(**dict(row))


def _normalize_label(raw_label: Any) -> int:
    """여러 입력 라벨 표현을 0 또는 1로 통일한다."""
    if isinstance(raw_label, bool):
        return 1 if raw_label else 0

    if isinstance(raw_label, int):
        if raw_label in (0, 1):
            return raw_label
        raise ValueError("label은 0 또는 1이어야 합니다.")

    normalized = str(raw_label).strip().lower()
    if normalized in {"1", "phishing", "voice_phishing", "fraud", "true", "피싱", "보이스피싱"}:
        return 1
    if normalized in {"0", "normal", "safe", "false", "정상"}:
        return 0

    raise ValueError("label은 정상 0 또는 보이스피싱 1로 변환 가능해야 합니다.")
