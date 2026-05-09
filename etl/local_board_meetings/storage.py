from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Meeting, StoredAgenda


SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    stable_id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL,
    board_name TEXT NOT NULL,
    meeting_type TEXT NOT NULL,
    meeting_date TEXT NOT NULL,
    start_time TEXT,
    timezone TEXT NOT NULL,
    location TEXT,
    virtual_url TEXT,
    source_page_url TEXT NOT NULL,
    agenda_url TEXT,
    agenda_label TEXT,
    confidence_notes TEXT,
    calendar_event_id TEXT,
    last_seen_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agendas (
    meeting_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    local_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    onedrive_web_url TEXT,
    PRIMARY KEY (meeting_id, source_url, sha256)
);

CREATE TABLE IF NOT EXISTS run_log (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    summary_json TEXT NOT NULL
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_meetings(conn: sqlite3.Connection, meetings: Iterable[Meeting], seen_at: datetime) -> tuple[int, int]:
    new_count = 0
    updated_count = 0
    for meeting in meetings:
        existing = conn.execute("SELECT payload_json FROM meetings WHERE stable_id = ?", (meeting.stable_id,)).fetchone()
        payload = json.dumps(_meeting_payload(meeting), sort_keys=True)
        if existing is None:
            new_count += 1
        elif existing["payload_json"] != payload:
            updated_count += 1
        conn.execute(
            """
            INSERT INTO meetings (
                stable_id, board_id, board_name, meeting_type, meeting_date, start_time, timezone,
                location, virtual_url, source_page_url, agenda_url, agenda_label, confidence_notes,
                last_seen_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(stable_id) DO UPDATE SET
                board_name=excluded.board_name,
                meeting_type=excluded.meeting_type,
                meeting_date=excluded.meeting_date,
                start_time=excluded.start_time,
                timezone=excluded.timezone,
                location=excluded.location,
                virtual_url=excluded.virtual_url,
                source_page_url=excluded.source_page_url,
                agenda_url=excluded.agenda_url,
                agenda_label=excluded.agenda_label,
                confidence_notes=excluded.confidence_notes,
                last_seen_at=excluded.last_seen_at,
                payload_json=excluded.payload_json
            """,
            (
                meeting.stable_id,
                meeting.board_id,
                meeting.board_name,
                meeting.meeting_type,
                meeting.meeting_date.isoformat(),
                meeting.start_time.isoformat() if meeting.start_time else "",
                meeting.timezone,
                meeting.location,
                meeting.virtual_url,
                meeting.source_page_url,
                meeting.agenda_url,
                meeting.agenda_label,
                meeting.confidence_notes,
                seen_at.isoformat(),
                payload,
            ),
        )
    conn.commit()
    return new_count, updated_count


def meetings_for_calendar(conn: sqlite3.Connection, today: datetime, lookahead_days: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM meetings
        WHERE date(meeting_date) >= date(?)
          AND date(meeting_date) <= date(?, '+' || ? || ' days')
        ORDER BY meeting_date, board_name, meeting_type
        """,
        (today.date().isoformat(), today.date().isoformat(), lookahead_days),
    ).fetchall()


def future_meetings(conn: sqlite3.Connection, today: datetime) -> list[Meeting]:
    rows = conn.execute(
        """
        SELECT * FROM meetings
        WHERE date(meeting_date) >= date(?)
        ORDER BY meeting_date, board_name, meeting_type
        """,
        (today.date().isoformat(),),
    ).fetchall()
    return [_row_to_meeting(row) for row in rows]


def set_calendar_event_id(conn: sqlite3.Connection, meeting_id: str, event_id: str) -> None:
    conn.execute("UPDATE meetings SET calendar_event_id = ? WHERE stable_id = ?", (event_id, meeting_id))
    conn.commit()


def agenda_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def agenda_exists(conn: sqlite3.Connection, meeting_id: str, source_url: str, sha256: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM agendas WHERE meeting_id = ? AND source_url = ? AND sha256 = ?",
        (meeting_id, source_url, sha256),
    ).fetchone()
    return row is not None


def save_agenda_record(conn: sqlite3.Connection, agenda: StoredAgenda) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO agendas (meeting_id, source_url, local_path, sha256, downloaded_at, onedrive_web_url)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            agenda.meeting_id,
            agenda.source_url,
            agenda.local_path,
            agenda.sha256,
            agenda.downloaded_at.isoformat(),
            agenda.onedrive_web_url,
        ),
    )
    conn.commit()


def write_run_log(conn: sqlite3.Connection, run_id: str, started_at: datetime, mode: str, summary: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO run_log (run_id, started_at, mode, summary_json) VALUES (?, ?, ?, ?)",
        (run_id, started_at.isoformat(), mode, json.dumps(summary, sort_keys=True)),
    )
    conn.commit()


def _meeting_payload(meeting: Meeting) -> dict[str, str]:
    data = asdict(meeting)
    data["meeting_date"] = meeting.meeting_date.isoformat()
    data["start_time"] = meeting.start_time.isoformat() if meeting.start_time else ""
    data["stable_id"] = meeting.stable_id
    return data


def _row_to_meeting(row: sqlite3.Row) -> Meeting:
    from datetime import date, datetime

    return Meeting(
        board_id=row["board_id"],
        board_name=row["board_name"],
        meeting_type=row["meeting_type"],
        meeting_date=date.fromisoformat(row["meeting_date"]),
        start_time=datetime.strptime(row["start_time"], "%H:%M:%S").time() if row["start_time"] else None,
        timezone=row["timezone"],
        location=row["location"] or "",
        virtual_url=row["virtual_url"] or "",
        source_page_url=row["source_page_url"],
        agenda_url=row["agenda_url"] or "",
        agenda_label=row["agenda_label"] or "",
        confidence_notes=row["confidence_notes"] or "",
    )
