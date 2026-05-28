# skyward

Personal Python client + MCP server for Skyward Family Access at Jordan School
District (`skystu.jordan.k12.ut.us`). Pulls classes, term grades, and per-class
assignments. Built for one student; not generalized across districts.

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

Add the following to `~/.zshrc`:

```sh
export SKYWARD_USERNAME="furrchr000"
export SKYWARD_PASSWORD="<your-skyward-password>"
export SKYWARD_BASE_URL="https://skystu.jordan.k12.ut.us/scripts/wsisa.dll/WService=wsEAplus"
```

(I tried to do this for you but the security guard declined writing to
`~/.zshrc`. The password is the one you shared — also rotate it if you want,
since it briefly lived in a conversation transcript.)

Then reload: `source ~/.zshrc`.

## Using it

### From Claude Code / Claude Desktop (MCP)

Already registered (`claude mcp list` should show `skyward ✓ Connected`).
Tools available:

- `skyward_summary` — one-row-per-class snapshot of the latest grade.
- `skyward_get_classes` — full per-term Q1..Q4 grid.
- `skyward_get_assignments(class_name, term="Q4")` — assignment breakdown.

The `~/.claude/skills/skyward` skill teaches Claude when to reach for these.

### From the shell (debug entry)

```sh
uv run python -m skyward.debug classes
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

## Not yet wired up

- Attendance (`sfattendance001.w`)
- Schedule (`sfschedule001.w`)
- Messages (the home page side panel + `sfmainhttp001.w?action=allEmailHistory`)
- Report card / academic history (`sfacademichistory001.w`)
- GPA (probably from academic history)
- Numeric percent for term grades (gradebook page only ships the letter; the
  percent appears on the assignment popup's Term Summary grid)

Each follows the same scrape pattern; the auth and request scaffolding are
already in place.

## Running tests

```sh
uv run pytest -q
```
