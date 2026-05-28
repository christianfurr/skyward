"""High-level Skyward Family Access client."""

from __future__ import annotations

import os
import time

from .auth import SkywardSession, login
from .exceptions import AuthError, NotLoggedIn, ScrapeError
from .models import Assignment, AttendanceDay, Class, GpaSummary, Message, ScheduleEntry
from .parsers.assignments import parse_assignments, parse_term_summary
from .parsers.attendance import parse_attendance
from .parsers.gpa import parse_gpa_details, parse_gpa_rank
from .parsers.gradebook import parse_gradebook
from .parsers.messages import parse_messages
from .parsers.schedule import parse_schedule

DEFAULT_BASE_URL = "https://skystu.jordan.k12.ut.us/scripts/wsisa.dll/WService=wsEAplus"


class SkywardClient:
    def __init__(
        self,
        username: str,
        password: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        min_request_interval: float = 1.0,
    ) -> None:
        self._username = username
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._session: SkywardSession | None = None
        self._min_interval = min_request_interval
        self._last_request: float = 0.0
        self._classes_cache: list[Class] | None = None

    @classmethod
    def from_env(cls) -> "SkywardClient":
        try:
            user = os.environ["SKYWARD_USERNAME"]
            pw = os.environ["SKYWARD_PASSWORD"]
        except KeyError as e:
            raise AuthError(f"Missing required env var: {e}") from e
        base = os.environ.get("SKYWARD_BASE_URL", DEFAULT_BASE_URL)
        return cls(user, pw, base_url=base)

    def login(self) -> None:
        self._session = login(self._base_url, self._username, self._password)

    def close(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self) -> "SkywardClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _ensure_session(self) -> SkywardSession:
        if self._session is None:
            self.login()
        if self._session is None:
            raise NotLoggedIn("Login did not produce a session")
        return self._session

    def _throttle(self) -> None:
        wait = self._last_request + self._min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _post(
        self,
        path: str,
        *,
        extra: dict[str, str] | None = None,
        referer: str | None = None,
        xhr: bool = False,
        retry_on_expiry: bool = True,
    ) -> str:
        sess = self._ensure_session()
        self._throttle()
        body = sess.xhr_form(extra) if xhr else sess.auth_form(extra)
        headers: dict[str, str] = {}
        if referer:
            headers["Referer"] = f"{sess.base_url}/{referer}"
        if xhr:
            headers["X-Requested-With"] = "XMLHttpRequest"
        r = sess.client.post(f"{sess.base_url}/{path}", data=body, headers=headers or None)
        if r.status_code != 200:
            raise ScrapeError(f"HTTP {r.status_code}", url=path, snippet=r.text[:300])

        text = r.text
        if _looks_expired(text) and retry_on_expiry:
            self._session = None
            self._classes_cache = None
            return self._post(path, extra=extra, referer=referer, xhr=xhr, retry_on_expiry=False)
        return text

    def get_classes(self, *, refresh: bool = False) -> list[Class]:
        if self._classes_cache is None or refresh:
            html = self._post("sfgradebook001.w")
            self._classes_cache = parse_gradebook(html)
        return self._classes_cache

    def get_assignments(self, class_name_or_id: str, term: str = "TERM 4") -> list[Assignment]:
        classes = self.get_classes()
        cls = _resolve_class(classes, class_name_or_id)
        if cls is None:
            available = ", ".join(c.name for c in classes)
            raise ScrapeError(f"No class matching {class_name_or_id!r}. Available: {available}")

        grade = _resolve_term(cls, term)
        if grade is None or grade.gb_id is None:
            available = ", ".join(g.term for g in cls.grades)
            raise ScrapeError(
                f"No graded term {term!r} for {cls.name}. Available terms: {available}"
            )

        sess = self._ensure_session()
        xml = self._post(
            "httploader.p?file=sfgradebook001.w",
            referer="sfgradebook001.w",
            xhr=True,
            extra={
                "action":                 "viewGradeInfoDialog",
                "gridCount":              "1",
                "fromHttp":               "yes",
                "stuId":                  sess.params.get("nameid", ""),
                "entityId":               cls.entity_id or "",
                "corNumId":               cls.class_id,
                "track":                  cls.track or "0",
                "section":                cls.section or "",
                "gbId":                   grade.gb_id,
                "bucket":                 grade.bucket or term,
                "subjectId":              "",
                "dialogLevel":            "1",
                "isEoc":                  "no",
                "ishttp":                 "true",
                "javascript.filesAdded":  "jquery.1.8.2.js,qsfmain001.css,sfgradebook.css,qsfmain001.min.js,sfgradebook.js,sfprint001.js",
                "requestId":              str(int(time.time() * 1000)),
            },
        )
        # While we have the popup, opportunistically backfill the numeric
        # percent on the cached term grade. The gradebook landing page only
        # ships the letter, so this is the cheapest way to get the percent.
        _letter, percent = parse_term_summary(xml)
        if percent is not None and grade.percent is None:
            grade.percent = percent

        return parse_assignments(xml)

    def get_attendance(self) -> list[AttendanceDay]:
        html = self._post("sfattendance001.w")
        return parse_attendance(html)

    def get_schedule(self) -> list[ScheduleEntry]:
        html = self._post("sfschedule001.w")
        return parse_schedule(html)

    def get_messages(self) -> list[Message]:
        html = self._post("sfhome01.w")
        return parse_messages(html)

    def get_gpa(self, *, school_year: int | None = None) -> GpaSummary:
        """Fetch cumulative GPA + (optionally) the per-term breakdown for a year.

        The cumulative call returns one row per GPA type (Normal, Weighted,
        ...). If `school_year` is given (e.g. 2026 for the 2025-2026 year), a
        second call fills in the per-term breakdown.
        """
        sess = self._ensure_session()
        # An entity_id is needed; pick the first one we know about from the
        # gradebook. Falls back to the Skyward default ("710" for Riverton)
        # only if no classes are cached yet — almost never the case in
        # practice.
        entity_id = next((c.entity_id for c in self.get_classes() if c.entity_id), None)
        common = {
            "stuId":                  sess.params.get("nameid", ""),
            "entityId":               entity_id or "",
            "ishttp":                 "true",
            "javascript.filesAdded":  "jquery.1.8.2.js,qsfmain001.css,sfgradebook.css,qsfmain001.min.js,sfgradebook.js,sfprint001.js",
        }

        rank_xml = self._post(
            "httploader.p?file=sfgradebook002.w",
            referer="sfgradebook001.w",
            xhr=True,
            extra={
                **common,
                "action":    "viewGPARank",
                "requestId": str(int(time.time() * 1000)),
            },
        )
        rows = parse_gpa_rank(rank_xml)

        summary = GpaSummary(rows=rows)
        if school_year is not None:
            details_xml = self._post(
                "httploader.p?file=sfgradebook002.w",
                referer="sfgradebook001.w",
                xhr=True,
                extra={
                    **common,
                    "action":     "viewGPADetails",
                    "schoolyear": str(school_year),
                    "requestId":  str(int(time.time() * 1000)),
                },
            )
            summary.term_breakdown = parse_gpa_details(details_xml)
            summary.school_year = school_year
        return summary


def _looks_expired(text: str) -> bool:
    return "session has expired" in text.lower() or (
        "tryLogin" in text and "skyporthttp.w" in text and len(text) < 50_000
    )


def _resolve_class(classes: list[Class], needle: str) -> Class | None:
    n = needle.strip().lower()
    for c in classes:
        if c.class_id == needle:
            return c
    matches = [c for c in classes if n in c.name.lower()]
    return matches[0] if len(matches) == 1 else None


def _resolve_term(cls: Class, term: str) -> "type | None":  # type: ignore[valid-type]
    t = term.strip().lower()
    for g in cls.grades:
        if g.term.lower() == t or (g.bucket or "").lower() == t:
            return g
    return None
