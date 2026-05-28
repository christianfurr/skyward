# skyward

Python client + MCP server + Claude skill for [Skyward Family Access][skyward].
Pulls classes, term grades, and per-class assignment breakdowns.

Default target is Jordan SD (`skystu.jordan.k12.ut.us`); base URL is an env
var so it can point at any Skyward district. Personal project — not affiliated
with Skyward or any school district.

[skyward]: https://www.skyward.com/family-access

## Layout

```
src/skyward/
  auth.py            login flow + SkywardSession
  client.py          SkywardClient (the public surface)
  parsers/
    gradebook.py     parses the class/grade grid
    assignments.py   parses the per-class assignment popup
  mcp_server.py      FastMCP stdio server
  debug.py           dev-only entry point: `python -m skyward.debug ...`
skill/
  SKILL.md           Claude skill (symlinked into ~/.claude/skills/skyward)
tests/               pytest, hand-built fixtures (no real student data committed)
```

## Setup (one-time)

Add the following to `~/.zshrc` (or `~/.bashrc`):

```sh
export SKYWARD_USERNAME="<your-skyward-username>"
export SKYWARD_PASSWORD="<your-skyward-password>"
export SKYWARD_BASE_URL="https://skystu.jordan.k12.ut.us/scripts/wsisa.dll/WService=wsEAplus"
```

Then reload: `source ~/.zshrc`.

For another Skyward district, change `SKYWARD_BASE_URL` to that district's
`WService=...` base path. The login flow is the same across all districts
running the standard Skyward Family Access skin; the gradebook parser is
keyed off CSS conventions Skyward uses everywhere.

## Using it

### From Claude Code / Claude Desktop (MCP)

Already registered (`claude mcp list` should show `skyward ✓ Connected`).
Tools available:

- `skyward_summary` — one-row-per-class snapshot of the latest grade.
- `skyward_get_classes` — full per-term Q1..Q4 grid.
- `skyward_get_assignments(class_name, term="Q4")` — assignment breakdown.
  Side effect: backfills the numeric percent on the corresponding `TermGrade`.
- `skyward_get_attendance` — absence / tardy / check-out history (date, status, period, class, reason).
- `skyward_get_schedule` — current schedule (period, class, teacher, room, days).
- `skyward_get_messages` — home-page message feed (sender, subject, date, unread).
- `skyward_get_gpa(school_year=None)` — cumulative GPA + earned/failed credits;
  pass a `school_year` (e.g. 2026) for the per-quarter breakdown.

The `~/.claude/skills/skyward` skill teaches Claude when to reach for these.

### From the shell (debug entry)

```sh
uv run python -m skyward.debug classes
uv run python -m skyward.debug attendance
uv run python -m skyward.debug schedule
uv run python -m skyward.debug messages
uv run python -m skyward.debug gpa --year 2026
uv run python -m skyward.debug assignments "LANG ARTS" --term Q4
```

### As a library

```python
from skyward import SkywardClient

with SkywardClient.from_env() as c:
    for cls in c.get_classes():
        print(cls.name, [(g.term, g.letter) for g in cls.grades])
    asns = c.get_assignments("LANG ARTS", term="Q4")
```

## Auth flow (notes for future-me)

Skyward Family Access has no API. The login flow:

1. `POST /skyporthttp.w` with form body
   `requestAction=eel&codeType=tryLogin&codeValue=<u>&login=<u>&password=<p>`.
   Response is a `<li>v0^v1^...^v14</li>` caret-delimited blob. Index 14 is
   `encses`, indices 1 and 2 are joined by a literal `\x15` byte to form
   `sessionid`. Other indices populate `dwd`, `wfaacl`, `nameid`, etc.
2. `POST /sfhome01.w` with the parsed params to finalize the session.

For page-load endpoints (`sfgradebook001.w`, `sfattendance001.w`, etc.) only
`sessionid` + `encses` are needed in the form body.

For AJAX endpoints (`httploader.p?file=...`) the request also needs:

- `dwd`, `wfaacl` in the form body
- `Referer` and `X-Requested-With: XMLHttpRequest` headers
- `stuId = nameid` (NOT `web-data-recid` — that's a separate row id)
- `entityId` from `data-eId` on the gradebook grade cells (school-wide, 710 for
  Riverton High)
- the per-grade `corNumId`, `track`, `section`, `gbId`, `bucket` (all available
  via the gradebook parser)

If Skyward starts returning empty CDATA for assignment requests, check those
fields and headers first — that's exactly the failure mode we already debugged
in v0.

## GPA (notes for future-me)

GPA does *not* live on the Academic History page (that page is empty for this
account). It comes from the gradebook's "Display Options → GPA" dialog, which
fires two AJAX calls against `sfgradebook002.w`:

- `action=viewGPARank` → cumulative GPA by type + earned/failed credits.
  Response is `grid_CumulativeHistoricalGpaDialog<sid>_<eid>` with section
  rows ("2025 - 2026 School Year") interleaved with data rows.
- `action=viewGPADetails&schoolyear=<YYYY>` → per-term GPA for that school
  year. Response is `grid_GpaDetailsDialog_<sid>_<eid>` with `Term N (Type)`
  labels.

Both calls use the standard XHR form body (`sessionid`, `encses`, `dwd`,
`wfaacl`) plus `stuId=nameid` and `entityId`.

## Not yet wired up

- Full Academic History across school years. `sfacademichistory001.w` returns
  "Academic History is not available for CHRISTIAN" for this account and the
  `grid_gradeGrid_*` blocks load via AJAX we haven't reverse-engineered.
- Report card PDFs. `sfreportcards001.w` and `sfportfolio.w` were probed and
  returned "Unable to find the web object file specified" for this account.
- Full email message bodies. The home-page feed parser gives metadata only;
  Skyward lazy-loads bodies into `span#messageText_*`. The
  `sfmainhttp001.w?action=allEmailHistory` action returns the full dialog
  HTML but needs the right XHR headers — same pattern as the assignment
  popup, just unbuilt.

## Running tests

```sh
uv run pytest -q
```
