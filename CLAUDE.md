# CLAUDE.md

## Project overview

- **Name:** Yiji
- **Purpose:** Personal finance app
- **Stack:** python + fastAPI, NiceGUI, enablebanking.com
- **Package manager:** uv

### Project Description

One-page personal finance app. Pulls transaction history from bank accounts via enablebanking.com and shows it as graphs with filters.

### Key commands

```bash
uv run python -m app                             # run the app (http://127.0.0.1:8100; port via YIJI_PORT)
uv run ruff check . && uv run ruff format --check .  # lint + format check
uv run pyright                                   # type check
uv run pytest                                    # unit tests
uv run pytest -m e2e                             # end-to-end tests (first: uv run playwright install chromium)
```
---

## Comments

- Write self-explanatory code; do not comment what the code already says.
- Comment only the **why**: non-obvious decisions, workarounds, business rules, links to issues/specs.
- No commented-out code, no changelog-style comments ("added by…", "fixed…"), no section banners.
- Public API docs (JSDoc/docstrings) only for exported/public symbols, and only when the signature isn't enough.

## Prefer existing libraries over custom code

- Before writing a utility, check (in this order):
  1. The standard library / platform APIs.
  2. Dependencies already in the project (`pyproject.toml`).
  3. Well-maintained, widely used libraries.
- Build a custom solution only when no suitable option exists, or the dependency cost (size, licence, maintenance) clearly outweighs the benefit. State the reason in the PR description.
- Do not add a new dependency without mentioning it explicitly in your summary. Never add two libraries that solve the same problem.

## Testing

### Unit tests
- **Always load the `writing-tests` skill before writing or changing unit tests** and follow it.
- Every new feature or bug fix comes with unit tests; a bug fix starts with a failing test that reproduces it.
- Unit tests live in `tests/unit`.

### E2E tests
- Framework: Playwright (pytest-playwright), located in `tests/e2e`.
- Test **user flows**, not implementation details; one file per feature/flow (`test_<feature>.py`, marked `pytest.mark.e2e`).
- Select elements by role, label or `data-testid` — never by CSS classes or DOM structure.
- No fixed sleeps/timeouts; use the framework's auto-waiting and assertions.
- Each test is independent: sets up and cleans up its own data (via API/fixtures, not via the UI where avoidable).
- Use Page Objects / helpers in `tests/e2e/pages` for repeated interactions.
- Cover the happy path plus key failure paths (validation errors, unauthorized access, empty states).

## BUG Fixing

- Fix the root cause of a bug, not its symptom: a workaround leaves the defect in place for the next caller.

## UI and design

- **Always load the `ui-design` skill before creating or changing any UI.** It is the source of truth for components, spacing, typography and the colour palette.
- Use only design tokens / theme variables from the skill — no hard-coded colours, font sizes or spacing values.
- Every UI must be responsive and meet WCAG 2.1 AA (contrast, keyboard navigation, labels, focus states).

## Input validation

- **Validate all user-provided data** — forms, query/path params, request bodies, headers, file uploads, env vars, CLI args and data from external APIs.
- Validate at the boundary (on the server even if the client also validates) using Pydantic v2 models (`pydantic-settings` for env vars); share schemas between client and server where possible.
- Whitelist, don't blacklist: define allowed types, lengths, ranges and formats.
- Never trust client data for authorization decisions.
- Use parameterized queries / the ORM — never build SQL, shell commands or HTML from raw input.
- Return clear, user-safe error messages; never leak stack traces or internals.

## VS Code MCP tools

- When the VS Code MCP server is available, **prefer it over manual edits / grep** for:
  - **Refactoring:** rename symbol, extract function/variable, move file, organize imports — so all references update safely.
  - **Diagnostics:** fetch errors/warnings from the language server after every change and fix them before finishing.
  - **Navigation:** go to definition, find references, find implementations.
- Fall back to manual edits only when no MCP tool covers the operation.

## Code conventions

- **Always follow the `python-conventions` skill** for naming and style. Load it before writing code.
- If the skill and existing code disagree, follow the skill and flag the inconsistency instead of silently spreading the old pattern.
- Formatting is handled by `ruff format` — don't hand-format.
- Never hardcode values that someone might want to change without editing code. Put them in one central configuration location and read them from there.

# Wiki

- Save project architecture and use instructions to wiki using /project-wiki skill. Do it everytime you update feature or create new one. 

---

## Definition of done

Lint, format, type check, unit and e2e tests are run by the Stop hook (`.claude/hooks/run-checks.py`), which blocks finishing until they pass.

- [ ] New/changed logic covered by unit tests; user flows covered by E2E where relevant
- [ ] No unnecessary comments, no dead code
- [ ] Summary lists any new dependencies and open questions