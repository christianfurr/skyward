from datetime import date, datetime

from pydantic import BaseModel, Field


class TermGrade(BaseModel):
    term: str
    letter: str | None = None
    percent: float | None = None
    bucket: str | None = Field(default=None, description="Skyward bucket label (e.g. 'TERM 1')")
    gb_id: str | None = Field(default=None, description="Skyward gradebook record ID for fetching assignments")


class Class(BaseModel):
    class_id: str = Field(description="Skyward internal course identifier (corNumId)")
    name: str
    period: str | None = None
    teacher: str | None = None
    track: str | None = None
    section: str | None = None
    entity_id: str | None = Field(default=None, description="Skyward school entity id (eId)")
    grades: list[TermGrade] = Field(default_factory=list)


class Assignment(BaseModel):
    name: str
    category: str | None = None
    due_date: date | None = None
    score: str | None = Field(default=None, description="Raw score string from Skyward (e.g. '18/20', 'M', '*')")
    points_earned: float | None = None
    points_possible: float | None = None
    percent: float | None = None
    letter: str | None = None
    missing: bool = False


class AttendanceDay(BaseModel):
    day: date
    status: str
    period: str | None = None
    reason: str | None = None


class ScheduleEntry(BaseModel):
    period: str
    class_name: str
    teacher: str | None = None
    room: str | None = None
    days: str | None = None


class Message(BaseModel):
    subject: str
    sender: str | None = None
    sent_at: datetime | None = None
    body: str | None = None
    unread: bool = False


class GpaSummary(BaseModel):
    unweighted: float | None = None
    weighted: float | None = None
    as_of: date | None = None
