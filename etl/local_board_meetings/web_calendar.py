from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Meeting

CALENDAR_TITLE = "California Local Workforce Board Meetings"


def write_web_calendar(output_dir: Path, meetings: list[Meeting], generated_at: datetime) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    future = sorted(
        [meeting for meeting in meetings if meeting.meeting_date >= generated_at.date()],
        key=lambda m: (m.meeting_date, m.start_time or datetime.min.time(), m.board_name, m.meeting_type),
    )
    ics_path = output_dir / "calendar.ics"
    html_path = output_dir / "index.html"
    ics_path.write_text(render_ics(future, generated_at), encoding="utf-8")
    html_path.write_text(render_html(future, generated_at), encoding="utf-8")
    return html_path, ics_path


def render_ics(meetings: list[Meeting], generated_at: datetime) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CWA//Local Board Meeting Monitor//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_text(CALENDAR_TITLE)}",
        "X-WR-TIMEZONE:America/Los_Angeles",
    ]
    stamp = _utc_stamp(generated_at)
    for meeting in meetings:
        start = datetime.combine(meeting.meeting_date, meeting.start_time or datetime.min.time().replace(hour=9))
        end = start + timedelta(hours=1)
        description = "\n".join(
            [
                f"Source page: {meeting.source_page_url}",
                f"Agenda URL: {meeting.agenda_url or 'Not found yet'}",
                f"Location: {meeting.location or 'Not published'}",
                f"Virtual link: {meeting.virtual_url or 'Not published'}",
                f"Confidence notes: {meeting.confidence_notes}",
            ]
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{_ics_text(meeting.stable_id)}@cwa-local-board-meetings",
                f"DTSTAMP:{stamp}",
                f"DTSTART;TZID=America/Los_Angeles:{start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=America/Los_Angeles:{end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{_ics_text(f'{meeting.board_name} - {meeting.meeting_type}')}",
                f"LOCATION:{_ics_text(meeting.location or meeting.virtual_url)}",
                f"DESCRIPTION:{_ics_text(description)}",
                f"URL:{meeting.agenda_url or meeting.source_page_url}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold_ics(line) for line in lines) + "\r\n"


def render_html(meetings: list[Meeting], generated_at: datetime) -> str:
    rows = "\n".join(_meeting_row(meeting) for meeting in meetings)
    if not rows:
        rows = '<tr><td colspan="5">No future meetings discovered yet.</td></tr>'
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(CALENDAR_TITLE)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1c2430;
      --muted: #5d6a7a;
      --line: #d8dee7;
      --band: #f5f7fa;
      --accent: #0b6f85;
      --warn: #9a5b00;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: white;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 24px clamp(16px, 4vw, 48px);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(24px, 3vw, 34px);
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
    }}
    main {{
      padding: 24px clamp(16px, 4vw, 48px) 48px;
    }}
    .actions {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 20px;
    }}
    .actions a {{
      color: white;
      background: var(--accent);
      text-decoration: none;
      padding: 10px 14px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 12px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--band);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    a {{
      color: var(--accent);
    }}
    .missing {{
      color: var(--warn);
      font-weight: 600;
    }}
    @media (max-width: 720px) {{
      table, thead, tbody, tr, th, td {{
        display: block;
      }}
      thead {{
        display: none;
      }}
      tr {{
        border-bottom: 1px solid var(--line);
        padding: 10px 0;
      }}
      td {{
        border: 0;
        padding: 5px 0;
      }}
      td::before {{
        content: attr(data-label) ": ";
        color: var(--muted);
        font-weight: 700;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(CALENDAR_TITLE)}</h1>
    <div class="meta">Generated {html.escape(generated_at.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}</div>
  </header>
  <main>
    <div class="actions">
      <a href="calendar.ics">Subscribe / download ICS</a>
    </div>
    <table>
      <thead>
        <tr>
          <th>Date</th>
          <th>Board</th>
          <th>Meeting Type</th>
          <th>Agenda</th>
          <th>Source</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
  </main>
</body>
</html>
"""


def _meeting_row(meeting: Meeting) -> str:
    agenda = (
        f'<a href="{html.escape(meeting.agenda_url)}">Agenda</a>'
        if meeting.agenda_url
        else '<span class="missing">Missing</span>'
    )
    return f"""<tr>
  <td data-label="Date">{html.escape(meeting.meeting_date.isoformat())}</td>
  <td data-label="Board">{html.escape(meeting.board_name)}</td>
  <td data-label="Meeting Type">{html.escape(meeting.meeting_type)}</td>
  <td data-label="Agenda">{agenda}</td>
  <td data-label="Source"><a href="{html.escape(meeting.source_page_url)}">Source</a></td>
</tr>"""


def _utc_stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ics_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\r", "")
    )


def _fold_ics(line: str) -> str:
    if len(line) <= 75:
        return line
    chunks = [line[:75]]
    line = line[75:]
    while line:
        chunks.append(" " + line[:74])
        line = line[74:]
    return "\r\n".join(chunks)
