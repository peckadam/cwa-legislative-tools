from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Meeting

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
CALENDAR_NAME = "California Local Workforce Board Meetings"


class GraphConfigError(RuntimeError):
    pass


class GraphClient:
    def __init__(self, token: str) -> None:
        self.token = token

    @classmethod
    def from_env(cls) -> "GraphClient":
        token = os.getenv("MS_GRAPH_ACCESS_TOKEN") or _refresh_token_from_env()
        if not token:
            raise GraphConfigError(
                "Set MS_GRAPH_ACCESS_TOKEN or MS_GRAPH_TENANT_ID, MS_GRAPH_CLIENT_ID, "
                "MS_GRAPH_CLIENT_SECRET, and MS_GRAPH_REFRESH_TOKEN for live mode."
            )
        return cls(token)

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, data: bytes | None = None) -> dict[str, Any]:
        url = path if path.startswith("https://") else f"{GRAPH_BASE}{path}"
        body = data if data is not None else (json.dumps(payload).encode("utf-8") if payload is not None else None)
        headers = {"Authorization": f"Bearer {self.token}"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        return json.loads(raw.decode("utf-8")) if raw else {}

    def ensure_calendar(self, name: str = CALENDAR_NAME) -> str:
        calendars = self.request("GET", "/me/calendars?$select=id,name").get("value", [])
        for calendar in calendars:
            if calendar.get("name") == name:
                return calendar["id"]
        created = self.request("POST", "/me/calendars", {"name": name})
        return created["id"]

    def upload_file(self, local_path: Path, drive_path: str) -> dict[str, Any]:
        content = local_path.read_bytes()
        quoted = urllib.parse.quote(drive_path.strip("/"))
        if len(content) <= 4 * 1024 * 1024:
            return self.request("PUT", f"/me/drive/root:/{quoted}:/content", data=content)
        session = self.request("POST", f"/me/drive/root:/{quoted}:/createUploadSession", {"item": {"@microsoft.graph.conflictBehavior": "replace"}})
        upload_url = session["uploadUrl"]
        chunk_size = 320 * 1024 * 10
        result: dict[str, Any] = {}
        for start in range(0, len(content), chunk_size):
            chunk = content[start : start + chunk_size]
            end = start + len(chunk) - 1
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Length": str(len(chunk)),
                "Content-Range": f"bytes {start}-{end}/{len(content)}",
            }
            req = urllib.request.Request(upload_url, data=chunk, headers=headers, method="PUT")
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
                result = json.loads(raw.decode("utf-8")) if raw else {}
        return result

    def upsert_event(self, calendar_id: str, meeting: Meeting, existing_event_id: str = "", onedrive_web_url: str = "") -> str:
        payload = meeting_to_event_payload(meeting, onedrive_web_url)
        if existing_event_id:
            updated = self.request("PATCH", f"/me/calendars/{calendar_id}/events/{existing_event_id}", payload)
            return updated.get("id", existing_event_id)
        created = self.request("POST", f"/me/calendars/{calendar_id}/events", payload)
        return created["id"]


def meeting_to_event_payload(meeting: Meeting, onedrive_web_url: str = "") -> dict[str, Any]:
    start_dt = datetime.combine(meeting.meeting_date, meeting.start_time or datetime.min.time().replace(hour=9))
    end_dt = start_dt + timedelta(hours=1)
    body_lines = [
        f"Source page: {meeting.source_page_url}",
        f"Agenda URL: {meeting.agenda_url or 'Not found yet'}",
        f"OneDrive agenda: {onedrive_web_url or 'Not uploaded yet'}",
        f"Location: {meeting.location or 'Not published'}",
        f"Virtual link: {meeting.virtual_url or 'Not published'}",
        f"Confidence notes: {meeting.confidence_notes}",
        f"Stable external ID: {meeting.stable_id}",
    ]
    return {
        "subject": f"{meeting.board_name} - {meeting.meeting_type}",
        "isReminderOn": False,
        "showAs": "busy",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": meeting.timezone},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": meeting.timezone},
        "location": {"displayName": meeting.location or meeting.virtual_url or ""},
        "body": {"contentType": "Text", "content": "\n".join(body_lines)},
        "singleValueExtendedProperties": [
            {
                "id": "String {00020329-0000-0000-C000-000000000046} Name cwaLocalBoardMeetingId",
                "value": meeting.stable_id,
            }
        ],
    }


def _refresh_token_from_env() -> str:
    tenant = os.getenv("MS_GRAPH_TENANT_ID")
    client_id = os.getenv("MS_GRAPH_CLIENT_ID")
    client_secret = os.getenv("MS_GRAPH_CLIENT_SECRET")
    refresh_token = os.getenv("MS_GRAPH_REFRESH_TOKEN")
    if not all([tenant, client_id, refresh_token]):
        return ""
    form = {
        "client_id": client_id,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "offline_access User.Read Files.ReadWrite Calendars.ReadWrite",
    }
    if client_secret:
        form["client_secret"] = client_secret
    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["access_token"]
