"""Parser for the Skyward schedule page (`sfschedule001.w`).

Skyward renders the schedule as a matrix of per-period × per-term cells. Each
cell lives in a table whose id is
`grid_MATRIXStudentClasses_<sid>_<eid>_<period>_<term>`. The cell text is
`<a>CLASS NAME</a><br><a>TEACHER</a><br><span>Days A</span>&nbsp;&nbsp;Room 2410`.

The same class repeats across terms; we dedupe by (period, class_name) to
return one row per class.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..exceptions import ScrapeError
from ..models import ScheduleEntry

_SCHEDULE_GRID = re.compile(
    r"^grid_MATRIXStudentClasses_\d+_\d+_(?P<period>[^_]+)_(?P<term>\d+)$"
)
_ROOM = re.compile(r"Room\s+(\S+)", re.IGNORECASE)
_DAYS = re.compile(r"Days\s+(\S+)", re.IGNORECASE)


def parse_schedule(html: str) -> list[ScheduleEntry]:
    soup = BeautifulSoup(html, "lxml")
    tables = soup.find_all("table", id=_SCHEDULE_GRID)
    if not tables:
        raise ScrapeError(
            "No grid_MATRIXStudentClasses_* tables on schedule page",
            snippet=html[:300],
        )

    seen: set[tuple[str, str]] = set()
    out: list[ScheduleEntry] = []
    for table in tables:
        m = _SCHEDULE_GRID.match(table["id"])
        if not m:
            continue
        period = m.group("period")

        cell = table.find("td")
        if cell is None:
            continue
        links = cell.find_all("a")
        if not links:
            continue
        class_name = links[0].get_text(" ", strip=True)
        if not class_name:
            continue

        key = (period, class_name)
        if key in seen:
            continue
        seen.add(key)

        teacher = links[1].get_text(" ", strip=True) if len(links) > 1 else None
        cell_text = cell.get_text(" ", strip=True)
        days = _DAYS.search(cell_text)
        room = _ROOM.search(cell_text)

        out.append(
            ScheduleEntry(
                period=period,
                class_name=class_name,
                teacher=teacher or None,
                room=room.group(1) if room else None,
                days=days.group(1) if days else None,
            )
        )

    out.sort(key=_period_sort_key)
    return out


def _period_sort_key(entry: ScheduleEntry) -> tuple[int, str]:
    """Sort `1`, `2`, `3B`, `4` numerically when possible."""
    digits = "".join(ch for ch in entry.period if ch.isdigit())
    return (int(digits) if digits else 99, entry.period)
