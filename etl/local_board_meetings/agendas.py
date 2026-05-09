from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .fetcher import fetch_url
from .models import Meeting, StoredAgenda
from .storage import agenda_hash


def safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", value).strip(" .")


def agenda_folder(root: Path, meeting: Meeting) -> Path:
    return (
        root
        / safe_filename(meeting.board_name)
        / str(meeting.meeting_date.year)
        / safe_filename(f"{meeting.meeting_date.isoformat()} - {meeting.meeting_type}")
    )


def agenda_filename(meeting: Meeting) -> str:
    return safe_filename(f"{meeting.meeting_date.isoformat()} - {meeting.board_name} - {meeting.meeting_type} - Agenda.pdf")


def download_agenda(meeting: Meeting, output_root: Path, respect_robots: bool = True) -> StoredAgenda | None:
    if not meeting.agenda_url:
        return None
    page = fetch_url(meeting.agenda_url, respect_robots=respect_robots)
    content = page.body
    digest = agenda_hash(content)
    folder = agenda_folder(output_root, meeting)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / agenda_filename(meeting)
    if destination.exists() and agenda_hash(destination.read_bytes()) == digest:
        pass
    else:
        destination.write_bytes(content)
    return StoredAgenda(
        meeting_id=meeting.stable_id,
        source_url=meeting.agenda_url,
        local_path=str(destination),
        sha256=digest,
        downloaded_at=datetime.now(timezone.utc),
    )
