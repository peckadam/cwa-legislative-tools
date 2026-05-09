from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional


@dataclass(frozen=True)
class BoardSource:
    board_id: str
    board_name: str
    local_area: str
    main_website: str
    meeting_schedule_url: str
    agenda_minutes_url: str
    executive_committee_url: str
    notes: str
    last_checked_at: str
    confidence: str


@dataclass(frozen=True)
class AgendaLink:
    url: str
    label: str
    source_page_url: str


@dataclass(frozen=True)
class Meeting:
    board_id: str
    board_name: str
    meeting_type: str
    meeting_date: date
    start_time: Optional[time]
    timezone: str
    location: str
    virtual_url: str
    source_page_url: str
    agenda_url: str
    agenda_label: str
    confidence_notes: str

    @property
    def stable_id(self) -> str:
        normalized_type = "-".join(self.meeting_type.lower().split())
        return f"{self.board_id}:{normalized_type}:{self.meeting_date.isoformat()}"


@dataclass(frozen=True)
class StoredAgenda:
    meeting_id: str
    source_url: str
    local_path: str
    sha256: str
    downloaded_at: datetime
    onedrive_web_url: str = ""
