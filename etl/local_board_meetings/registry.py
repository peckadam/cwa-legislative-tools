from __future__ import annotations

import csv
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from .models import BoardSource

REGISTRY_COLUMNS = [
    "board_id",
    "board_name",
    "local_area",
    "main_website",
    "meeting_schedule_url",
    "agenda_minutes_url",
    "executive_committee_url",
    "notes",
    "last_checked_at",
    "confidence",
]


EXTRA_SEEDS = [
    {
        "local_area_name": "Mother Lode Workforce Development Board",
        "service_area": "Amador, Calaveras, Mariposa, and Tuolumne Counties",
        "website": "https://www.mljt.org/wdb",
    }
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "board"


def load_registry(path: Path, seed_manifest: Path | None = None) -> List[BoardSource]:
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            existing = [BoardSource(**row) for row in csv.DictReader(fh)]
        if seed_manifest and seed_manifest.exists():
            seeded = bootstrap_from_manifest(seed_manifest)
            by_id = {source.board_id: source for source in seeded}
            by_id.update({source.board_id: source for source in existing})
            merged = list(by_id.values())
            if len(merged) != len(existing):
                save_registry(path, merged)
            return merged
        return existing
    if not seed_manifest or not seed_manifest.exists():
        return []
    sources = bootstrap_from_manifest(seed_manifest)
    save_registry(path, sources)
    return sources


def save_registry(path: Path, sources: Iterable[BoardSource]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REGISTRY_COLUMNS)
        writer.writeheader()
        for source in sorted(sources, key=lambda s: s.board_name):
            writer.writerow(asdict(source))


def bootstrap_from_manifest(manifest_path: Path) -> List[BoardSource]:
    now = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, str]] = []
    with manifest_path.open(newline="", encoding="utf-8") as fh:
        rows.extend(csv.DictReader(fh))
    rows.extend(EXTRA_SEEDS)

    sources: list[BoardSource] = []
    seen: set[str] = set()
    for row in rows:
        name = row["local_area_name"].strip()
        board_id = slugify(name)
        if board_id in seen:
            continue
        seen.add(board_id)
        website = row["website"].strip()
        sources.append(
            BoardSource(
                board_id=board_id,
                board_name=name,
                local_area=row["service_area"].strip(),
                main_website=website,
                meeting_schedule_url=website,
                agenda_minutes_url=website,
                executive_committee_url="",
                notes="Bootstrapped from local official-board website manifest; discovery should confirm exact schedule, agenda/minutes, and executive committee pages.",
                last_checked_at=now,
                confidence="medium",
            )
        )
    return sources


def mark_checked(source: BoardSource, notes: str | None = None, confidence: str | None = None) -> BoardSource:
    data = asdict(source)
    data["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    if notes:
        data["notes"] = notes
    if confidence:
        data["confidence"] = confidence
    return BoardSource(**data)
