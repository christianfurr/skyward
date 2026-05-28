"""Parser for the Skyward gradebook landing page (`sfgradebook001.w`).

Skyward renders the gradebook as two parallel grids: a left "frozen" panel of
classDesc tables containing class name/period/teacher, and a scrolling right
panel of grade cells. The grade cells are not in the static HTML — they ship
inside JSON blobs in `<script>` tags and the page populates the grid client
side. We extract both pieces via regex on the raw HTML (BeautifulSoup can't
see the cells because they live in a JS string) and stitch them together by
the Skyward course ID (`cNI`).
"""

from __future__ import annotations

import html as html_mod
import re

from bs4 import BeautifulSoup

from ..exceptions import ScrapeError
from ..models import Class, TermGrade

_CLASS_TABLE_ID = re.compile(r"^classDesc_(\d+)_(\d+)_\d+_(\w+)$")

# The grade cells are embedded in JS-escaped HTML strings like
#   {"h":"<td ...><div class='gW_..._all'><a id=\'showGradeInfo\' ...
#   data-cNI=\'283184\' data-bkt=\'TERM 1\' data-lit=\'Q1\' ...>A<\/a> ...
# Quotes appear escaped (\') or plain depending on Skyward's JSON encoder; the
# pattern below tolerates both.
_GRADE_CELL = re.compile(
    r"id=\\?['\"]showGradeInfo\\?['\"][^>]*?"
    r"data-sId=\\?['\"](?P<sid>[^'\"]+)\\?['\"][^>]*?"
    r"data-eId=\\?['\"](?P<eid>[^'\"]+)\\?['\"][^>]*?"
    r"data-cNI=\\?['\"](?P<cni>[^'\"]+)\\?['\"][^>]*?"
    r"data-trk=\\?['\"](?P<trk>[^'\"]*)\\?['\"][^>]*?"
    r"data-sec=\\?['\"](?P<sec>[^'\"]*)\\?['\"][^>]*?"
    r"data-gId=\\?['\"](?P<gid>[^'\"]*)\\?['\"][^>]*?"
    r"data-bkt=\\?['\"](?P<bkt>[^'\"]*)\\?['\"][^>]*?"
    r"data-lit=\\?['\"](?P<lit>[^'\"]*)\\?['\"][^>]*?"
    r">(?P<letter>[^<]*)<"
)

_PERIOD_RE = re.compile(r"Period\s+(\S+)", re.IGNORECASE)


def _text(node) -> str:
    return " ".join(node.get_text(" ", strip=True).split())


def parse_gradebook(html: str) -> list[Class]:
    soup = BeautifulSoup(html, "lxml")

    classes: dict[str, Class] = {}

    for table in soup.find_all("table", id=_CLASS_TABLE_ID):
        m = _CLASS_TABLE_ID.match(table["id"])
        if not m:
            continue
        _sid, cni, _period_code = m.groups()
        if cni in classes:
            continue

        rows = table.find_all("tr", recursive=False)
        if not rows:
            continue

        name_anchor = rows[0].find("span", class_="classDesc")
        name = _text(name_anchor) if name_anchor else _text(rows[0])

        period = None
        if len(rows) > 1:
            ptext = _text(rows[1])
            pm = _PERIOD_RE.search(ptext)
            if pm:
                period = pm.group(1)

        teacher = None
        if len(rows) > 2:
            teacher = _text(rows[2]) or None

        classes[cni] = Class(class_id=cni, name=name, period=period, teacher=teacher)

    if not classes:
        raise ScrapeError("No classDesc_* tables found on gradebook page", snippet=html[:300])

    seen: set[tuple[str, str]] = set()
    for m in _GRADE_CELL.finditer(html):
        cni = m["cni"]
        cls = classes.get(cni)
        if cls is None:
            continue
        bkt = m["bkt"]
        key = (cni, bkt)
        if key in seen:
            continue
        seen.add(key)

        if cls.track is None:
            cls.track = m["trk"]
        if cls.section is None:
            cls.section = m["sec"]
        if cls.entity_id is None:
            cls.entity_id = m["eid"]

        letter_raw = html_mod.unescape(m["letter"]).strip()
        cls.grades.append(
            TermGrade(
                term=m["lit"] or bkt,
                bucket=bkt or None,
                letter=letter_raw or None,
                gb_id=m["gid"] or None,
            )
        )

    return list(classes.values())
