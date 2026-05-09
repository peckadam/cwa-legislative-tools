from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup

from .fetcher import absolute_url
from .models import AgendaLink, BoardSource, Meeting

MONTH_NAMES = "|".join(calendar.month_name[1:] + calendar.month_abbr[1:])
DATE_PATTERNS = [
    re.compile(rf"\b({MONTH_NAMES})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(20\d{{2}})\b", re.I),
    re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b"),
]
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)\b", re.I)
AGENDA_TERMS = ("agenda", "packet", "board packet")
MEETING_TERMS = ("meeting", "board", "committee", "agenda", "minutes", "calendar")
EXEC_TERMS = ("executive", "exec committee")
EXCLUDED_LINK_HOST_TERMS = ("facebook.com", "linkedin.com", "twitter.com", "x.com", "forms.office.com", "survey")


def parse_date(text: str) -> Optional[date]:
    text = " ".join(text.split())
    match = DATE_PATTERNS[0].search(text)
    if match:
        month = _month_number(match.group(1))
        return date(int(match.group(3)), month, int(match.group(2)))
    match = DATE_PATTERNS[1].search(text)
    if match:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    match = DATE_PATTERNS[2].search(text)
    if match:
        return date(int(match.group(3)), int(match.group(1)), int(match.group(2)))
    return None


def parse_time(text: str) -> Optional[time]:
    match = TIME_RE.search(text)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridian = match.group(3).lower()[0]
    if meridian == "p" and hour != 12:
        hour += 12
    if meridian == "a" and hour == 12:
        hour = 0
    return time(hour, minute)


def _month_number(value: str) -> int:
    normalized = value.strip(".").lower()
    for idx, name in enumerate(calendar.month_name):
        if name and name.lower() == normalized:
            return idx
    for idx, name in enumerate(calendar.month_abbr):
        if name and name.lower() == normalized:
            return idx
    raise ValueError(f"Unknown month {value}")


def extract_agenda_links(html: str, page_url: str) -> List[AgendaLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[AgendaLink] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        label = anchor.get_text(" ", strip=True)
        candidate = f"{label} {href}".lower()
        if any(term in candidate for term in AGENDA_TERMS) and (
            ".pdf" in candidate or "agenda" in candidate or "packet" in candidate
        ):
            links.append(AgendaLink(absolute_url(page_url, href), label or href, page_url))
    return _dedupe_agendas(links)


def find_candidate_pages(html: str, page_url: str) -> dict[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = {"meeting": [], "agenda": [], "executive": []}
    for anchor in soup.find_all("a", href=True):
        label = anchor.get_text(" ", strip=True)
        href = anchor["href"].strip()
        if href.startswith(("mailto:", "tel:", "#")):
            continue
        combined = f"{label} {href}".lower()
        url = absolute_url(page_url, href)
        if any(term in url.lower() for term in EXCLUDED_LINK_HOST_TERMS):
            continue
        if any(term in combined for term in MEETING_TERMS):
            candidates["meeting"].append(url)
        if any(term in combined for term in AGENDA_TERMS) or "minutes" in combined:
            candidates["agenda"].append(url)
        if any(term in combined for term in EXEC_TERMS):
            candidates["executive"].append(url)
    return {key: sorted(set(value)) for key, value in candidates.items()}


def extract_meetings(source: BoardSource, html: str, page_url: str, today: date, lookahead_days: int) -> List[Meeting]:
    soup = BeautifulSoup(html, "html.parser")
    agenda_links = extract_agenda_links(html, page_url)
    text_blocks = _candidate_text_blocks(soup)
    meetings: dict[str, Meeting] = {}
    max_date = today + timedelta(days=lookahead_days)
    for block in text_blocks:
        meeting_date = parse_date(block)
        if not meeting_date or meeting_date < today - timedelta(days=14) or meeting_date > max_date:
            continue
        meeting_type = infer_meeting_type(block)
        linked_agenda = best_agenda_for_date(agenda_links, meeting_date)
        meeting = Meeting(
            board_id=source.board_id,
            board_name=source.board_name,
            meeting_type=meeting_type,
            meeting_date=meeting_date,
            start_time=parse_time(block),
            timezone="America/Los_Angeles",
            location=infer_location(block),
            virtual_url=infer_virtual_url(block),
            source_page_url=page_url,
            agenda_url=linked_agenda.url if linked_agenda else "",
            agenda_label=linked_agenda.label if linked_agenda else "",
            confidence_notes="Extracted from official source page text; verify manually if the source page uses embedded calendars or PDFs.",
        )
        meetings[meeting.stable_id] = meeting
    return sorted(meetings.values(), key=lambda m: (m.meeting_date, m.board_name, m.meeting_type))


def infer_meeting_type(text: str) -> str:
    lowered = text.lower()
    if "executive" in lowered:
        return "Executive Committee"
    if "committee" in lowered:
        return "Committee"
    if "special" in lowered:
        return "Special Board Meeting"
    return "Board Meeting"


def infer_location(text: str) -> str:
    lowered = text.lower()
    if "zoom" in lowered or "teams" in lowered or "virtual" in lowered:
        return "Virtual"
    if "hybrid" in lowered:
        return "Hybrid"
    return ""


def infer_virtual_url(text: str) -> str:
    match = re.search(r"https?://\S+", text)
    return match.group(0).rstrip(").,") if match else ""


def best_agenda_for_date(links: Iterable[AgendaLink], meeting_date: date) -> Optional[AgendaLink]:
    tokens = {
        meeting_date.isoformat(),
        meeting_date.strftime("%m/%d/%Y"),
        meeting_date.strftime("%m-%d-%Y"),
        meeting_date.strftime("%Y%m%d"),
        meeting_date.strftime("%B %-d, %Y") if hasattr(meeting_date, "strftime") else "",
        meeting_date.strftime("%B %d, %Y"),
    }
    for link in links:
        haystack = f"{link.label} {link.url}".lower()
        if any(token and token.lower() in haystack for token in tokens):
            return link
    return None


def _candidate_text_blocks(soup: BeautifulSoup) -> list[str]:
    blocks: list[str] = []
    selectors = ["li", "tr", "p", "article", "div"]
    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if len(text) < 8 or len(text) > 800:
                continue
            if any(pattern.search(text) for pattern in DATE_PATTERNS):
                blocks.append(text)
    return blocks


def _dedupe_agendas(links: Iterable[AgendaLink]) -> list[AgendaLink]:
    seen: set[str] = set()
    output: list[AgendaLink] = []
    for link in links:
        if link.url in seen:
            continue
        seen.add(link.url)
        output.append(link)
    return output
