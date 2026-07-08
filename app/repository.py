"""Repository layer for voice phishing cases."""

from __future__ import annotations

import json
from typing import Any

from app.database import get_connection
from app.schemas import PhishingCase, PhishingCaseCreate


def insert_case(case: PhishingCaseCreate) -> int:
    """Insert one case and return its database id."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO phishing_cases(text, label, reason, source)
            VALUES (?, ?, ?, ?)
            """,
            (case.text.strip(), case.label, case.reason.strip(), case.source.strip()),
        )
        return int(cursor.lastrowid)


def get_case(case_id: int) -> PhishingCase:
    """Return one case by id."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, text, label, reason, source, created_at
            FROM phishing_cases
            WHERE id = ?
            """,
            (case_id,),
        ).fetchone()

    if row is None:
        raise ValueError(f"case_id={case_id} 사례를 찾을 수 없습니다.")

    return PhishingCase(**dict(row))


def insert_cases(cases: list[PhishingCaseCreate]) -> int:
    """Insert many cases in one transaction."""
    if not cases:
        return 0

    rows = [
        (case.text.strip(), case.label, case.reason.strip(), case.source.strip())
        for case in cases
    ]
    with get_connection() as connection:
        connection.executemany(
            """
            INSERT INTO phishing_cases(text, label, reason, source)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)


def list_cases(limit: int = 100) -> list[PhishingCase]:
    """Return recently stored cases."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, text, label, reason, source, created_at
            FROM phishing_cases
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [PhishingCase(**dict(row)) for row in rows]


def list_all_cases() -> list[PhishingCase]:
    """Return all cases for RAG retrieval."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, text, label, reason, source, created_at
            FROM phishing_cases
            ORDER BY id ASC
            """
        ).fetchall()

    return [PhishingCase(**dict(row)) for row in rows]


def parse_cases_json(raw_bytes: bytes) -> tuple[list[PhishingCaseCreate], int]:
    """
    Parse uploaded JSON bytes into normalized case objects.

    Supported formats:
    1. [{ "text": "...", "label": 1, "reason": "...", "source": "..." }]
    2. { "cases": [{ "text": "...", "label": 1 }] }
    """
    payload: Any = json.loads(raw_bytes.decode("utf-8-sig"))
    items = payload.get("cases", payload) if isinstance(payload, dict) else payload

    if not isinstance(items, list):
        raise ValueError("JSON은 리스트이거나 {'cases': [...]} 형식이어야 합니다.")

    cases: list[PhishingCaseCreate] = []
    skipped_count = 0

    for item in items:
        if not isinstance(item, dict):
            skipped_count += 1
            continue

        text = str(item.get("text", item.get("content", ""))).strip()
        label = item.get("label", item.get("is_phishing"))

        # is_phishing: true 같은 데이터도 label: 1 형태로 맞춘다.
        if isinstance(label, bool):
            label = 1 if label else 0

        try:
            normalized_label = int(label)
            case = PhishingCaseCreate(
                text=text,
                label=normalized_label,
                reason=str(item.get("reason", item.get("description", ""))),
                source=str(item.get("source", "")),
            )
        except Exception:
            skipped_count += 1
            continue

        cases.append(case)

    return cases, skipped_count
