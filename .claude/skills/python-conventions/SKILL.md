---
name: python-conventions
description: Conventions for Python code in this repository: naming, comments, docstrings, constants vs configuration, reuse and formatting. Load before writing or editing any Python.
---
# Python conventions

If this skill and existing code disagree, follow the skill and flag the inconsistency instead of spreading the old pattern.

## Naming
- Avoid single-letter variables except where obvious (`x`, `y`, …).
- Avoid names that differ by a single letter (`position` / `positions`).

## Comments and docstrings
- Write self-explanatory code; don't comment what the code already says.
- Comment only the **why**: non-obvious decisions, workarounds, business rules, links to issues or specs.
- No commented-out code, no changelog comments ("added by…", "fixed…"), no section banners.
- Docstrings only on public functions and classes, and only when the signature isn't enough.

## Values and configuration
- Anything someone might want to change without editing code (URLs, ports, limits, timeouts, paths) goes in `Settings` in `app/config.py`, read from `YIJI_*` env vars and validated by pydantic-settings. Credentials keep their provider's env names through `validation_alias` (`ENABLE_BANKING_APP_ID`, `OLLAMA_API_KEY`).
- Colors and fonts live in `app/ui/palette.py`; text shown to users lives in `app/texts.py`.
- Every other value stays local to its only user; a module-level constant is for something shared.

## Reuse
- Before writing a helper, a checker or a test fixture, look for an existing one to reuse or generalize: a near-copy of something already there is two things to keep in step.

## Formatting
- `ruff format` handles formatting; don't hand-format. Line length is 100.
