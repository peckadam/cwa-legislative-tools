from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from .models import Meeting


def missing_agendas_within_72h(meetings: list[Meeting], now: datetime) -> list[Meeting]:
    cutoff = now.date() + timedelta(days=3)
    return [
        meeting
        for meeting in meetings
        if now.date() <= meeting.meeting_date <= cutoff and not meeting.agenda_url
    ]


def build_summary(
    *,
    started_at: datetime,
    mode: str,
    boards_checked: int,
    meetings: list[Meeting],
    new_meetings: int,
    updated_meetings: int,
    events_updated: int,
    agendas_downloaded: int,
    failures: list[dict[str, str]],
) -> dict:
    missing = missing_agendas_within_72h(meetings, started_at)
    return {
        "started_at": started_at.isoformat(),
        "mode": mode,
        "boards_checked": boards_checked,
        "meetings_found": len(meetings),
        "new_meetings_added": new_meetings,
        "meetings_updated": updated_meetings,
        "events_updated": events_updated,
        "agendas_downloaded": agendas_downloaded,
        "missing_agendas_within_72_hours": [
            {
                "meeting_id": meeting.stable_id,
                "board_name": meeting.board_name,
                "meeting_type": meeting.meeting_type,
                "meeting_date": meeting.meeting_date.isoformat(),
                "source_page_url": meeting.source_page_url,
            }
            for meeting in missing
        ],
        "failures_requiring_human_review": failures,
    }


def write_reports(output_dir: Path, run_id: str, summary: dict, meetings: list[Meeting]) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{run_id}.json"
    md_path = output_dir / f"{run_id}.md"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_markdown(summary, meetings), encoding="utf-8")
    return json_path, md_path


def append_progress_log(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    failures = summary["failures_requiring_human_review"]
    missing = summary["missing_agendas_within_72_hours"]
    lines = [
        f"## {summary['started_at']} ({summary['mode']})",
        "",
        f"- Boards checked: {summary['boards_checked']}",
        f"- Meetings found: {summary['meetings_found']}",
        f"- Missing agendas within 72 hours: {len(missing)}",
        f"- Failures requiring human review: {len(failures)}",
    ]
    for failure in failures[:20]:
        lines.append(f"- Review: {failure.get('board_name', 'unknown')} - {failure.get('url', '')} - {failure.get('error', '')}")
    lines.append("")
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Local Board Meeting Monitor Progress Log\n\n"
    path.write_text(existing + "\n".join(lines) + "\n", encoding="utf-8")


def _markdown(summary: dict, meetings: list[Meeting]) -> str:
    lines = [
        "# Local Board Meeting Monitor Run Report",
        "",
        f"- Started: {summary['started_at']}",
        f"- Mode: {summary['mode']}",
        f"- Boards checked: {summary['boards_checked']}",
        f"- Meetings found: {summary['meetings_found']}",
        f"- New meetings added: {summary['new_meetings_added']}",
        f"- Events updated: {summary['events_updated']}",
        f"- Agendas downloaded: {summary['agendas_downloaded']}",
        f"- Missing agendas within 72 hours: {len(summary['missing_agendas_within_72_hours'])}",
        f"- Failures requiring human review: {len(summary['failures_requiring_human_review'])}",
        "",
        "## Meetings",
        "",
    ]
    if meetings:
        lines.append("| Date | Board | Type | Agenda | Source |")
        lines.append("|---|---|---|---|---|")
        for meeting in sorted(meetings, key=lambda m: (m.meeting_date, m.board_name)):
            agenda = meeting.agenda_url or "missing"
            lines.append(
                f"| {meeting.meeting_date.isoformat()} | {meeting.board_name} | {meeting.meeting_type} | {agenda} | {meeting.source_page_url} |"
            )
    else:
        lines.append("No meetings were extracted from the checked pages.")
    if summary["failures_requiring_human_review"]:
        lines.extend(["", "## Human Review"])
        for failure in summary["failures_requiring_human_review"]:
            lines.append(f"- {failure.get('board_name', 'unknown')}: {failure.get('url', '')} - {failure.get('error', '')}")
    return "\n".join(lines) + "\n"
