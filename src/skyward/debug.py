"""Tiny dev entry point: `uv run python -m skyward.debug <command>`.

Not a stable user-facing CLI — just enough to drive the client end-to-end
during development and verification.
"""

from __future__ import annotations

import argparse
import json
import sys

from .client import SkywardClient


def _classes_command(client: SkywardClient) -> int:
    classes = client.get_classes()
    for c in classes:
        grades = ", ".join(f"{g.term}={g.letter or '—'}" for g in c.grades)
        print(f"  P{c.period:<3} {c.name:<32} ({c.teacher})  {grades}")
    return 0


def _attendance_command(client: SkywardClient) -> int:
    for d in client.get_attendance():
        cls = d.class_name or "(multi)"
        reason = f" — {d.reason}" if d.reason else ""
        print(f"  {d.day}  P{d.period or '-':<4} {d.status:<32}{reason}  {cls}")
    return 0


def _schedule_command(client: SkywardClient) -> int:
    for e in client.get_schedule():
        teacher = e.teacher or "—"
        room = f"Room {e.room}" if e.room else ""
        days = f"Days {e.days}" if e.days else ""
        print(f"  P{e.period:<3} {e.class_name:<32} {teacher:<24} {days:<8} {room}")
    return 0


def _messages_command(client: SkywardClient) -> int:
    for m in client.get_messages():
        flag = "*" if m.unread else " "
        when = m.sent_at.isoformat(sep=" ", timespec="minutes") if m.sent_at else "—"
        sender = m.sender or "(system)"
        print(f"  {flag} {when}  {sender}  —  {m.subject}")
    return 0


def _gpa_command(client: SkywardClient, school_year: int | None) -> int:
    gpa = client.get_gpa(school_year=school_year)
    for r in gpa.rows:
        print(f"  {r.gpa_type:<12} GPA={r.cumulative_gpa}  earned={r.earned_credits}  failed={r.failed_credits}")
    if gpa.term_breakdown:
        print(f"\n  {gpa.school_year} breakdown:")
        for t in gpa.term_breakdown:
            print(f"    {t.label:<24} {t.gpa}")
    return 0


def _assignments_command(client: SkywardClient, class_name: str, term: str) -> int:
    asns = client.get_assignments(class_name, term=term)
    print(json.dumps([a.model_dump(mode="json") for a in asns], indent=2, default=str))
    return 0


def _raw_assignments_command(client: SkywardClient, class_name: str, term: str) -> int:
    """Dump the raw XML response from Skyward for debugging the assignment popup."""
    import time as _t

    classes = client.get_classes()
    cls = next((c for c in classes if class_name.lower() in c.name.lower()), None)
    assert cls is not None
    grade = next((g for g in cls.grades if g.term.lower() == term.lower()), None)
    assert grade is not None and grade.gb_id is not None

    sess = client._ensure_session()  # type: ignore[attr-defined]
    xml = client._post(  # type: ignore[attr-defined]
        "httploader.p?file=sfgradebook001.w",
        extra={
            "action":      "viewGradeInfoDialog",
            "gridCount":   "1",
            "fromHttp":    "yes",
            "stuId":       sess.params.get("web-data-recid", ""),
            "entityId":    cls.entity_id or "",
            "corNumId":    cls.class_id,
            "track":       cls.track or "0",
            "section":     cls.section or "",
            "gbId":        grade.gb_id,
            "bucket":      grade.bucket or term,
            "subjectId":   "",
            "dialogLevel": "1",
            "isEoc":       "no",
            "ishttp":      "true",
            "requestId":   str(int(_t.time() * 1000)),
        },
    )
    sys.stdout.write(xml)
    return 0


def _login_command(client: SkywardClient) -> int:
    client.login()
    sess = client._session  # type: ignore[attr-defined]
    assert sess is not None
    print(f"Logged in. encses={sess.encses[:6]}... params={sorted(sess.params)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skyward.debug")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login")
    sub.add_parser("classes")
    sub.add_parser("attendance")
    sub.add_parser("schedule")
    sub.add_parser("messages")
    g = sub.add_parser("gpa")
    g.add_argument("--year", type=int, default=None, help="School year for per-term breakdown (e.g. 2026)")
    a = sub.add_parser("assignments")
    a.add_argument("class_name", help="Substring of the class name, or exact class_id")
    a.add_argument("--term", default="Q4", help="Term label like Q1/Q2/Q3/Q4 or 'TERM 1' (default Q4)")
    raw = sub.add_parser("assignments-raw")
    raw.add_argument("class_name")
    raw.add_argument("--term", default="Q4")

    args = parser.parse_args(argv)
    client = SkywardClient.from_env()
    try:
        if args.cmd == "login":
            return _login_command(client)
        if args.cmd == "classes":
            return _classes_command(client)
        if args.cmd == "attendance":
            return _attendance_command(client)
        if args.cmd == "schedule":
            return _schedule_command(client)
        if args.cmd == "messages":
            return _messages_command(client)
        if args.cmd == "gpa":
            return _gpa_command(client, args.year)
        if args.cmd == "assignments":
            return _assignments_command(client, args.class_name, args.term)
        if args.cmd == "assignments-raw":
            return _raw_assignments_command(client, args.class_name, args.term)
    finally:
        client.close()
    return 1


if __name__ == "__main__":
    sys.exit(main())
