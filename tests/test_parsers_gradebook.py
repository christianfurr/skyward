from pathlib import Path

import pytest

from skyward.exceptions import ScrapeError
from skyward.parsers.gradebook import parse_gradebook

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def minimal_html() -> str:
    return (FIXTURES / "gradebook_minimal.html").read_text()


def test_parses_class_metadata(minimal_html: str) -> None:
    classes = parse_gradebook(minimal_html)
    assert len(classes) == 2
    bio = next(c for c in classes if c.class_id == "111111")
    assert bio.name == "BIOLOGY"
    assert bio.period == "2"
    assert bio.teacher == "TEACHER, ONE"


def test_parses_grade_cells_by_term_label(minimal_html: str) -> None:
    classes = parse_gradebook(minimal_html)
    bio = next(c for c in classes if c.class_id == "111111")
    assert [(g.term, g.letter) for g in bio.grades] == [("Q1", "A"), ("Q2", "B+")]


def test_handles_empty_letter_as_none(minimal_html: str) -> None:
    classes = parse_gradebook(minimal_html)
    lang = next(c for c in classes if c.class_id == "222222")
    grades = {g.term: g.letter for g in lang.grades}
    assert grades["Q1"] == "C"
    assert grades["Q2"] is None


def test_raises_on_html_without_classes() -> None:
    with pytest.raises(ScrapeError):
        parse_gradebook("<html><body>nope</body></html>")
