"""Parser for the Skyward attendance history page (`sfattendance001.w`).

Skyward renders attendance history as a single table whose id starts with
`grid_attendanceHistory`. Columns are: Date | Attendance | Period | Class.
The Date column uses the format `Wed May 27, 2026`. A `View Classes` link
appears when the absence spans multiple periods.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..exceptions import ScrapeError
from ..models import AttendanceDay

_ATTENDANCE_GRID = re.compile(r"^grid_attendanceHistory")
_PAREN = re.compile(r"\s*\(([^)]*)\)\s*$")


def _parse_date(text: str) -> date | None:
    text = text.strip()
    if not text:
        return None
    for fmt in ("%a %b %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _split_status(text: str) -> tuple[str, str | None]:
    """`Check-in/out (Check-out)` -> (`Check-in/out`, `Check-out`)."""
    m = _PAREN.search(text)
    if not m:
        return text.strip(), None
    return _PAREN.sub("", text).strip(), m.group(1).strip()


def parse_attendance(html: str) -> list[AttendanceDay]:
    soup = BeautifulSoup(html, "lxml")
    grid = soup.find("table", id=_ATTENDANCE_GRID)
    if grid is None:
        raise ScrapeError(
            "No grid_attendanceHistory table on attendance page", snippet=html[:300]
        )

    body = grid.find("tbody") or grid
    out: list[AttendanceDay] = []
    for row in body.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        day = _parse_date(cells[0].get_text(" ", strip=True))
        if day is None:
            continue
        status, reason = _split_status(cells[1].get_text(" ", strip=True))
        period = cells[2].get_text(" ", strip=True) or None
        class_text = cells[3].get_text(" ", strip=True)
        class_name = class_text or None
        # `View Classes` is a link aggregating multi-period absences — not a class.
        if class_name and class_name.lower() == "view classes":
            class_name = None

        out.append(
            AttendanceDay(
                day=day,
                status=status,
                period=period,
                class_name=class_name,
                reason=reason,
            )
        )
    return out
