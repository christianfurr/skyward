"""Skyward MCP stdio server.

Exposes Skyward grades and assignments as MCP tools that Claude (Desktop or
Code) can call. Reads SKYWARD_USERNAME / SKYWARD_PASSWORD / SKYWARD_BASE_URL
from the environment.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import SkywardClient
from .exceptions import SkywardError

mcp = FastMCP("skyward")

_client: SkywardClient | None = None


def _get() -> SkywardClient:
    global _client
    if _client is None:
        _client = SkywardClient.from_env()
    return _client


@mcp.tool()
def skyward_get_classes() -> list[dict[str, Any]]:
    """List the user's current Skyward classes with per-term letter grades.

    Returns one entry per class. Each entry includes the class name, period,
    teacher, and a `grades` list of `{term, letter}` records (e.g. Q1=A, Q2=B+).
    Use this first to discover which classes exist; pass the class name into
    `skyward_get_assignments` to drill into a specific class.
    """
    try:
        return [c.model_dump(mode="json") for c in _get().get_classes(refresh=True)]
    except SkywardError as e:
        return [{"error": str(e)}]


@mcp.tool()
def skyward_get_assignments(class_name: str, term: str = "Q4") -> list[dict[str, Any]]:
    """Fetch the per-assignment breakdown for a specific class and term.

    `class_name` is a substring of the class name as shown by `skyward_get_classes`
    (e.g. "BIOLOGY" or "Lang Arts"). `term` is the Skyward term label, defaulting
    to the most recent quarter "Q4"; valid values include Q1/Q2/Q3/Q4.

    Returns one entry per assignment, with name, category (e.g. weight bucket),
    due_date (YYYY-MM-DD), score (raw "X out of Y" string), points_earned,
    points_possible, percent, letter grade, and a `missing` flag.
    """
    try:
        asns = _get().get_assignments(class_name, term=term)
        return [a.model_dump(mode="json") for a in asns]
    except SkywardError as e:
        return [{"error": str(e)}]


@mcp.tool()
def skyward_summary() -> dict[str, Any]:
    """One-shot snapshot of the user's current academic standing.

    Returns a dict with `classes` (each with the latest non-empty term grade)
    and any assignment failures or missing items pulled across recent terms.
    Useful as a single-call answer to "how am I doing in school?".
    """
    try:
        classes = _get().get_classes(refresh=True)
    except SkywardError as e:
        return {"error": str(e)}

    summary = []
    for c in classes:
        latest = next((g for g in reversed(c.grades) if g.letter), None)
        summary.append(
            {
                "class":   c.name,
                "period":  c.period,
                "teacher": c.teacher,
                "term":    latest.term if latest else None,
                "letter":  latest.letter if latest else None,
            }
        )
    return {"classes": summary}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
