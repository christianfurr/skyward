"""Parser for the Skyward GPA dialogs.

Both endpoints are served by `httploader.p?file=sfgradebook002.w` with
`action=viewGPARank` (cumulative across years) or `action=viewGPADetails`
(per-term within one school year). Each returns an XML envelope whose
`<output>` CDATA block contains a grid table.

`viewGPARank` → `grid_CumulativeHistoricalGpaDialog<sid>_<eid>`
    Section rows ("2025 - 2026 School Year") interleave with data rows
    (GPA Type | Cumulative GPA | Earned Credits | Failed Credits).

`viewGPADetails` → `grid_GpaDetailsDialog_<sid>_<eid>`
    Two columns: term label, GPA value.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..exceptions import ScrapeError
from ..models import GpaRow, GpaTermRow

_CDATA_OUTPUT = re.compile(r"<output><!\[CDATA\[(.*?)\]\]></output>", re.DOTALL)
_RANK_GRID = re.compile(r"^grid_CumulativeHistoricalGpaDialog")
_DETAILS_GRID = re.compile(r"^grid_GpaDetailsDialog_")


def _maybe_float(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _inner(xml: str) -> str:
    m = _CDATA_OUTPUT.search(xml)
    return m.group(1) if m else xml


def parse_gpa_rank(xml: str) -> list[GpaRow]:
    soup = BeautifulSoup(_inner(xml), "lxml")
    grid = soup.find("table", id=_RANK_GRID)
    if grid is None:
        raise ScrapeError(
            "No grid_CumulativeHistoricalGpaDialog table in GPA response",
            snippet=xml[:300],
        )
    body = grid.find("tbody") or grid
    out: list[GpaRow] = []
    for row in body.find_all("tr", recursive=False):
        if "sf_Section" in (row.get("class") or []):
            # School-year header row, no GPA value.
            continue
        cells = row.find_all("td", recursive=False)
        if len(cells) < 4:
            continue
        out.append(
            GpaRow(
                gpa_type=cells[0].get_text(" ", strip=True),
                cumulative_gpa=_maybe_float(cells[1].get_text(" ", strip=True)),
                earned_credits=_maybe_float(cells[2].get_text(" ", strip=True)),
                failed_credits=_maybe_float(cells[3].get_text(" ", strip=True)),
            )
        )
    return out


def parse_gpa_details(xml: str) -> list[GpaTermRow]:
    soup = BeautifulSoup(_inner(xml), "lxml")
    grid = soup.find("table", id=_DETAILS_GRID)
    if grid is None:
        raise ScrapeError(
            "No grid_GpaDetailsDialog table in GPA details response",
            snippet=xml[:300],
        )
    body = grid.find("tbody") or grid
    out: list[GpaTermRow] = []
    for row in body.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        if len(cells) < 2:
            continue
        out.append(
            GpaTermRow(
                label=cells[0].get_text(" ", strip=True),
                gpa=_maybe_float(cells[1].get_text(" ", strip=True)),
            )
        )
    return out
