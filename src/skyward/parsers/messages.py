"""Parser for the Skyward home-page message feed.

The home page (`sfhome01.w`) renders a `MessageFeed` <ul> with one `.messageWrap`
per item. Each wrap carries:

  div.messageHead .text    sender / class header
  div.messageBody .date    date string e.g. `Wed May 20, 2026  9:27pm`
  div.messageBody .Subject subject (absent for non-class messages)
  class `home_unread`      on the wrap when the message hasn't been read

Skyward lazy-loads message bodies into `span#messageText_*`, so the static HTML
gives us metadata only. That's fine for the use case: "show me what messages
I have".
"""

from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from ..models import Message

_DATE_FMTS = (
    "%a %b %d, %Y %I:%M%p",
    "%a %b %d, %Y  %I:%M%p",
    "%b %d, %Y %I:%M%p",
)


def _parse_date(text: str) -> datetime | None:
    text = " ".join(text.split())  # collapse repeated whitespace
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_messages(html: str) -> list[Message]:
    soup = BeautifulSoup(html, "lxml")
    wraps = soup.select("div.messageWrap")
    out: list[Message] = []
    for wrap in wraps:
        head = wrap.select_one("div.messageHead .text")
        body = wrap.select_one("div.messageBody")
        sender = head.get_text(" ", strip=True) if head else None

        subject_el = body.select_one(".Subject") if body else None
        subject = subject_el.get_text(" ", strip=True) if subject_el else (sender or "(no subject)")
        # Non-class messages (e.g. "Payment made to Food Service Account")
        # repeat the sender as the subject. Skyward puts the headline in `.text`
        # of the head and there's no separate Subject — keep sender as None to
        # avoid duplicating the same string in both fields.
        if subject_el is None:
            sender = None

        date_el = body.select_one(".date") if body else None
        sent_at = _parse_date(date_el.get_text(" ", strip=True)) if date_el else None

        unread = "home_unread" in (wrap.get("class") or [])

        out.append(
            Message(
                subject=subject,
                sender=sender,
                sent_at=sent_at,
                body=None,
                unread=unread,
            )
        )
    return out
