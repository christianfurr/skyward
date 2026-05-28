from datetime import date
from pathlib import Path

import pytest

from skyward.exceptions import ScrapeError
from skyward.parsers.assignments import parse_assignments

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_xml() -> str:
    return (FIXTURES / "assignments_minimal.xml").read_text()


def test_parses_real_assignment_rows(minimal_xml: str) -> None:
    asns = parse_assignments(minimal_xml)
    assert len(asns) == 3
    essay, missing, midterm = asns

    assert essay.name == "Essay Final"
    assert essay.due_date == date(2026, 5, 17)
    assert essay.points_earned == 20.0
    assert essay.points_possible == 20.0
    assert essay.percent == 100.0
    assert essay.letter == "A"
    assert essay.missing is False

    assert midterm.due_date == date(2026, 5, 1)
    assert midterm.letter == "B"


def test_categories_propagate_to_following_rows(minimal_xml: str) -> None:
    asns = parse_assignments(minimal_xml)
    essay, missing, midterm = asns
    assert essay.category == "Assignment weighted at 50.00%"
    assert missing.category == "Assignment weighted at 50.00%"
    assert midterm.category == "Test weighted at 50.00%"


def test_missing_flag(minimal_xml: str) -> None:
    asns = parse_assignments(minimal_xml)
    _, missing, _ = asns
    assert missing.missing is True
    assert missing.percent == 0.0


def test_raises_on_empty_response() -> None:
    empty = "<?xml version='1.0'?><response><output><![CDATA[]]></output></response>"
    with pytest.raises(ScrapeError):
        parse_assignments(empty)
