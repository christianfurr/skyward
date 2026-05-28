---
name: skyward
description: Use when the user asks about their Skyward Family Access grades, assignments, classes, teachers, or how they're doing in school at Jordan SD / Riverton High. Routes Skyward questions through the local MCP server.
---

# Skyward (Jordan School District)

This user has a Python-based Skyward client + MCP server at `~/Code/skyward/`. When the user asks anything about grades, assignments, teachers, class standing, or "how am I doing in [class]?", use the MCP tools — don't try to scrape the web UI yourself.

## Available MCP tools (server name: `skyward`)

| Tool | Use when |
|---|---|
| `skyward_summary` | First call for vague questions like "how am I doing" or "what are my grades right now" — returns one row per class with the most recent letter grade. |
| `skyward_get_classes` | When you need the full per-term grid (Q1/Q2/Q3/Q4 letters per class), or to look up the exact class name before pulling assignments. |
| `skyward_get_assignments` | When the user asks why a grade is what it is, what's missing, or about a specific assignment. Requires a `class_name` substring (e.g. "Lang Arts") and optional `term` (defaults to "Q4"). |

## Conventions

- Terms are labeled `Q1`, `Q2`, `Q3`, `Q4`. The current term is whichever Skyward has the latest non-empty letter for.
- `class_name` accepts a substring match — "biology" resolves to "BIOLOGY".
- An assignment with `missing: true` is what's actually pulling a grade down; surface those first when explaining a low grade.
- Categories like "Assignment weighted at 50.00%" are weight buckets, not assignment names.

## When NOT to use this skill

- Other districts' Skyward instances (this client is configured for Jordan SD only).
- Questions about attendance, schedule, or messages — those endpoints aren't wired up yet; tell the user that and offer to add them.
- Login/password/account changes — read-only client.
