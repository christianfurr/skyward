---
name: skyward
description: Use when the user asks about their Skyward Family Access grades, assignments, attendance, schedule, teachers, messages, or how they're doing in school at Jordan SD / Riverton High. Routes Skyward questions through the local MCP server.
---

# Skyward (Jordan School District)

This user has a Python-based Skyward client + MCP server at `~/Code/skyward/`. When the user asks anything about grades, assignments, attendance, schedule, teachers, messages, or class standing, use the MCP tools — don't try to scrape the web UI yourself.

## Available MCP tools (server name: `skyward`)

| Tool | Use when |
|---|---|
| `skyward_summary` | First call for vague questions like "how am I doing" or "what are my grades right now" — returns one row per class with the most recent letter grade and (if cached) percent. |
| `skyward_get_classes` | When you need the full per-term grid (Q1/Q2/Q3/Q4 letters per class), or to look up the exact class name before pulling assignments. |
| `skyward_get_assignments` | When the user asks why a grade is what it is, what's missing, or about a specific assignment. Requires a `class_name` substring (e.g. "Lang Arts") and optional `term` (defaults to "Q4"). Also backfills the numeric percent on the term grade. |
| `skyward_get_attendance` | When the user asks about absences, tardies, check-outs, "how often have I been late", or anything attendance-related. Returns one entry per attendance event, newest first. |
| `skyward_get_schedule` | When the user asks what classes they have, in what period, with what teacher, in what room. Returns one entry per class sorted by period. |
| `skyward_get_messages` | When the user asks about messages, announcements, or "what did my teacher send" — pulls the home-page message feed (sender, subject, date, unread flag). Bodies are not included; Skyward lazy-loads them. |
| `skyward_get_gpa` | When the user asks "what's my GPA", "am I valedictorian material", or about credits earned. Returns cumulative GPA (typically `Normal` for Jordan SD) plus, when `school_year` is supplied (e.g. 2026 for the 2025-2026 year), a per-quarter GPA breakdown. |

## Conventions

- Terms are labeled `Q1`, `Q2`, `Q3`, `Q4`. The current term is whichever Skyward has the latest non-empty letter for.
- `class_name` accepts a substring match — "biology" resolves to "BIOLOGY".
- An assignment with `missing: true` is what's actually pulling a grade down; surface those first when explaining a low grade.
- Categories like "Assignment weighted at 50.00%" are weight buckets, not assignment names.
- Attendance status strings look like `Unexcused Tardy`, `Guardian-excused Absence`, `Check-in/out`. A parenthesized sub-reason (e.g. `(Check-out)`, `(Counselor meeting)`) is split out into the `reason` field.
- A `class_name: null` on an attendance row means the absence spanned multiple periods (Skyward shows "View Classes" instead of a specific class).

## KPHS (online) classes — exclude from grade reporting

Classes prefixed `KPHS/` (Kings Peak High School, the district's online school) are
enrollment placeholders in this Skyward entity. They carry **no gradebook**:
`grades: []`, and `entity_id`, `section`, `track`, `gb_id` are all `null`.
`skyward_get_assignments` on one returns `No graded term ... Available terms: `.

- **Omit them from grade tables and "how am I doing" answers.** Do not list them with a
  blank/em-dash grade as if a grade were pending — there is nothing to pull, ever.
- Their teacher field is garbage and must not be reported:
  - `skyward_get_classes` / `skyward_summary` return `LAURA ADAMS` (note the `First Last`
    format vs `LAST, FIRST` for real classes) — the KPHS coordinator, not the instructor.
  - `skyward_get_schedule` returns the *course name* in the `teacher` column
    (`WEB DEVELOPMENT 1`, `V FINANCIAL LITERACY`) — a column-shift artifact.
- Real grades for these live in the KPHS system, not Skyward. If asked, say so rather than
  reporting a blank.
- They may still appear in schedule/period listings (periods 27 and 32) — that's fine;
  the exclusion is about grades and teachers only.

## When NOT to use this skill

- Other districts' Skyward instances (this client is configured for Jordan SD only).
- Full academic history across school years — the Academic History page is gated for this account. Use `skyward_get_gpa` instead for cumulative + per-term GPA.
- Report card PDFs — not wired up.
- Login/password/account changes — read-only client.
