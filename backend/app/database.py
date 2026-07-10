"""보이스피싱 학습 데이터와 통화 로그를 저장하는 SQLite 도우미."""

from __future__ import annotations

import sqlite3

from backend.app.paths import DATA_DIR, DB_PATH


def get_connection() -> sqlite3.Connection:
    """컬럼 이름으로 접근할 수 있는 SQLite 연결을 생성한다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    """필요한 테이블이 없으면 새로 생성한다."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS training_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT DEFAULT '',
                text TEXT NOT NULL,
                label INTEGER NOT NULL CHECK (label IN (0, 1)),
                source TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_training_cases_label
            ON training_cases(label)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS training_case_turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                turn_index INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'unknown',
                text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES training_cases(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_training_case_turns_case_id
            ON training_case_turns(case_id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id INTEGER,
                name TEXT DEFAULT '',
                file_type TEXT NOT NULL DEFAULT 'realtime',
                status TEXT NOT NULL DEFAULT 'normal',
                risk_score REAL NOT NULL DEFAULT 0,
                risk_level TEXT NOT NULL DEFAULT 'low',
                detected_label INTEGER NOT NULL DEFAULT 0 CHECK (detected_label IN (0, 1)),
                phishing_type TEXT DEFAULT '',
                core_evidence TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_column(connection, "call_logs", "file_type", "TEXT NOT NULL DEFAULT 'realtime'")
        _ensure_column(connection, "call_logs", "phishing_type", "TEXT DEFAULT ''")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS call_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER NOT NULL,
                turn_index INTEGER NOT NULL,
                role TEXT NOT NULL DEFAULT 'unknown',
                content TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (log_id) REFERENCES call_logs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_call_messages_log_id
            ON call_messages(log_id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS detection_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER NOT NULL,
                risk_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                detected_label INTEGER NOT NULL CHECK (detected_label IN (0, 1)),
                core_evidence TEXT NOT NULL,
                matched_patterns TEXT DEFAULT '[]',
                retrieved_case_ids TEXT DEFAULT '[]',
                model_version TEXT DEFAULT 'rag-v1',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (log_id) REFERENCES call_logs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_detection_results_log_id
            ON detection_results(log_id)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sent',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (log_id) REFERENCES call_logs(id) ON DELETE CASCADE
            )
            """
        )


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """기존 SQLite DB에 새 컬럼이 없으면 안전하게 추가한다."""
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_column_names = {column["name"] for column in columns}
    if column_name in existing_column_names:
        return

    connection.execute(
        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
    )
