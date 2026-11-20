---
name: committing
description: Use when committing, pushing or opening a PR in this repository. Covers the commit message, the pre-commit checks and what stays out of a commit.
---

- **Branches:** Use `main` unless specified otherwise. 
- **Commits:** follow [Conventional Commits](https://www.conventionalcommits.org/):
  `<type>(<scope>): <imperative summary, ≤72 chars>`
  Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`, `build`.
- One logical change per commit; keep commits small and buildable.
- Before committing: lint, type check and tests must pass.
- Never commit secrets, `.env` files, credentials or generated build artifacts.
- **Do not** commit, push, rebase, force-push, reset, or delete branches unless explicitly asked.
- Never rewrite history on shared branches. Never use `--no-verify`.
- PRs: short description of *what* and *why*, notes on testing and any new dependencies.