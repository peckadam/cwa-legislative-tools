from __future__ import annotations

import unittest
from datetime import date, time

from etl.local_board_meetings.extraction import extract_agenda_links, extract_meetings, parse_date, parse_time
from etl.local_board_meetings.graph import meeting_to_event_payload
from etl.local_board_meetings.models import BoardSource, Meeting
from etl.local_board_meetings.storage import agenda_hash
from etl.local_board_meetings.web_calendar import render_ics


class LocalBoardMeetingTests(unittest.TestCase):
    def test_parse_common_date_formats(self) -> None:
        self.assertEqual(parse_date("Board Meeting: May 14, 2026 at 9:00 AM"), date(2026, 5, 14))
        self.assertEqual(parse_date("Executive Committee 2026-06-02"), date(2026, 6, 2))
        self.assertEqual(parse_date("Agenda for 7/8/2026"), date(2026, 7, 8))

    def test_parse_time(self) -> None:
        self.assertEqual(parse_time("10:30 a.m."), time(10, 30))
        self.assertEqual(parse_time("1 PM"), time(13, 0))

    def test_agenda_link_detection(self) -> None:
        html = """
        <a href="/files/2026-05-14-agenda.pdf">May 14, 2026 Board Agenda</a>
        <a href="/contact">Contact</a>
        <a href="packet.pdf">Board Packet</a>
        """
        links = extract_agenda_links(html, "https://example.gov/wdb")
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].url, "https://example.gov/files/2026-05-14-agenda.pdf")

    def test_duplicate_meeting_stable_id(self) -> None:
        source = BoardSource(
            board_id="sample-wdb",
            board_name="Sample WDB",
            local_area="Sample County",
            main_website="https://example.gov",
            meeting_schedule_url="https://example.gov",
            agenda_minutes_url="https://example.gov",
            executive_committee_url="",
            notes="test",
            last_checked_at="",
            confidence="high",
        )
        html = """
        <ul>
          <li>Board Meeting May 14, 2026 9:00 AM <a href="2026-05-14-agenda.pdf">Agenda</a></li>
          <li>Board Meeting May 14, 2026 9:00 AM</li>
        </ul>
        """
        meetings = extract_meetings(source, html, "https://example.gov/meetings", date(2026, 5, 1), 180)
        self.assertEqual(len(meetings), 1)
        self.assertEqual(meetings[0].stable_id, "sample-wdb:board-meeting:2026-05-14")

    def test_agenda_hash_is_stable(self) -> None:
        self.assertEqual(agenda_hash(b"agenda"), agenda_hash(b"agenda"))
        self.assertNotEqual(agenda_hash(b"agenda"), agenda_hash(b"changed agenda"))

    def test_calendar_event_mapping(self) -> None:
        meeting = Meeting(
            board_id="sample-wdb",
            board_name="Sample WDB",
            meeting_type="Executive Committee",
            meeting_date=date(2026, 5, 14),
            start_time=time(13, 30),
            timezone="America/Los_Angeles",
            location="Virtual",
            virtual_url="https://example.gov/zoom",
            source_page_url="https://example.gov/meetings",
            agenda_url="https://example.gov/agenda.pdf",
            agenda_label="Agenda",
            confidence_notes="high confidence",
        )
        payload = meeting_to_event_payload(meeting, "https://onedrive.live.com/agenda")
        self.assertEqual(payload["subject"], "Sample WDB - Executive Committee")
        self.assertEqual(payload["start"]["dateTime"], "2026-05-14T13:30:00")
        self.assertEqual(payload["start"]["timeZone"], "America/Los_Angeles")
        self.assertIn("sample-wdb:executive-committee:2026-05-14", payload["body"]["content"])

    def test_ics_feed_contains_stable_event(self) -> None:
        meeting = Meeting(
            board_id="sample-wdb",
            board_name="Sample WDB",
            meeting_type="Board Meeting",
            meeting_date=date(2026, 5, 14),
            start_time=time(9, 0),
            timezone="America/Los_Angeles",
            location="Room 1",
            virtual_url="",
            source_page_url="https://example.gov/meetings",
            agenda_url="https://example.gov/agenda.pdf",
            agenda_label="Agenda",
            confidence_notes="test",
        )
        ics = render_ics([meeting], __import__("datetime").datetime(2026, 5, 1, tzinfo=__import__("datetime").timezone.utc))
        self.assertIn("BEGIN:VCALENDAR", ics)
        self.assertIn("UID:sample-wdb:board-meeting:2026-05-14@cwa-local-board-meetings", ics)
        self.assertIn("SUMMARY:Sample WDB - Board Meeting", ics)


if __name__ == "__main__":
    unittest.main()
