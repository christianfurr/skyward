"""Parser for the per-class assignment popup.

The endpoint returns an XML envelope with an `<output>` CDATA block containing
the HTML grid. Each row in `grid_stuAssignmentSummaryGrid_<sid>_<cni>_..._<bucketNum>`
is either a category-summary row (no date, text like "Assignment weighted at X%")
or a real assignment row with a date in `MM/DD/YY` format.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from bs4 import BeautifulSoup

from ..exceptions import ScrapeError
from ..models import Assignment

_CDATA_OUTPUT = re.compile(r"<output><!\[CDATA\[(.*?)\]\]></output>", re.DOTALL)
_POINTS = re.compile(r"^\s*([\d.]+)\s+out of\s+([\d.]+)\s*$", re.IGNORECASE)
_ASSIGNMENT_GRID = re.compile(r"^grid_stuAssignmentSummaryGrid_")
_DATE = re.compile(r"^\d{2}/\d{2}/\d{2,4}$")


def _maybe_date(text: str) -> date | None:
    text = text.strip()
    if not _DATE.fullmatch(text):
        return None
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _maybe_float(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_assignments(xml: str) -> list[Assignment]:
    m = _CDATA_OUTPUT.search(xml)
    inner = m.group(1) if m else xml

    soup = BeautifulSoup(inner, "lxml")
    grid = soup.find("table", id=_ASSIGNMENT_GRID)
    if grid is None:
        raise ScrapeError("No assignment grid in popup response", snippet=inner[:300])

    body = grid.find("tbody") or grid
    rows = body.find_all("tr", recursive=False)

    current_category: str | None = None
    out: list[Assignment] = []

    for row in rows:
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td", recursive=False)]
        if not cells:
            continue

        due = _maybe_date(cells[0]) if len(cells) > 0 else None
        if due is None:
            # Treat as a category-header / summary row. Skyward writes things like
            # "Assignment weighted at 50.00%" — keep the row text as the category
            # for assignments that follow.
            label = cells[1] if len(cells) > 1 else cells[0]
            current_category = label or current_category
            continue

        # Real assignment row. Columns vary slightly by district config but the
        # canonical layout we've observed is:
        # [Due, Assignment, Grade(letter), Score(%), Points (e.g. "18 out of 20"), Missing, NoCount, Absent]
        name = cells[1] if len(cells) > 1 else ""
        letter = cells[2] if len(cells) > 2 else None
        percent = _maybe_float(cells[3]) if len(cells) > 3 else None

        earned = possible = None
        if len(cells) > 4:
            pm = _POINTS.match(cells[4])
            if pm:
                earned, possible = float(pm.group(1)), float(pm.group(2))

        missing_flag = bool(cells[5].strip()) if len(cells) > 5 else False

        out.append(
            Assignment(
                name=name,
                category=current_category,
                due_date=due,
                score=cells[4] if len(cells) > 4 else None,
                points_earned=earned,
                points_possible=possible,
                percent=percent,
                letter=(letter or None),
                missing=missing_flag,
            )
        )

    return out
