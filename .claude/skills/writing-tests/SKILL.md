---
name: writing-tests
description: Use when writing or updating any test in tests/ (unit or E2E/Playwright), adding coverage for new code, changing page objects or fixtures, or fixing a bug that needs a regression test. Covers this repo's test style, shared fakes, parallel-safe E2E tests and naming.
---

# Writing tests

Test end to end: enter through the highest public entry point and fake only the system boundaries. A test proves a behaviour the user (or calling system) sees, not how the code gets there.

## Framework and layout

- **Unit:** pytest, in `tests/unit/test_<module>.py`. Enter through the public function or the FastAPI app via `fastapi.testclient.TestClient(app)` (from `app.main`).
- **E2E:** Playwright via pytest-playwright, in `tests/e2e/test_<feature>.py`, every file marked `pytestmark = pytest.mark.e2e`. The session-scoped `base_url` fixture in `tests/e2e/conftest.py` starts the real app with uvicorn on a free port; tests use the `page` fixture and relative URLs.
- **Page objects:** `tests/e2e/pages/<page>_page.py`; select by role, label or `data-testid`, never by CSS class or DOM structure; assert with `playwright.sync_api.expect` (auto-waits).
- Shared fixtures go in the nearest `conftest.py`; reuse or generalize an existing fixture before adding one.
- Use `pytest.mark.parametrize` for input/expected tables, not copy-pasted tests.

## What every test file must cover

1. The documented happy path
2. Every error path the caller can see: raised exceptions, validation errors, error responses
3. The boundaries the code actually branches on (empty input and empty states, limits, invalid values)
4. If fixing a bug: write the failing regression test FIRST, then the fix

## Naming

- Test names state behaviour, not implementation: `test_rejects_invoice_with_negative_total`, never `test_works`
- Regression tests cite the issue in the docstring: "Empty line items (#482)."

## Mocking policy

- Mock at system boundaries only: network, filesystem, clock, randomness
- NEVER mock the module under test or its pure helpers
- Control time through an injected clock or a fixture; never sleep in a test
- Patch with `monkeypatch` so changes are undone after each test

## E2E: independent and wait-free

- E2E tests run in parallel (`-n auto`, pytest-xdist); each worker starts its own app and fakes. Never rely on test order, a fixed port or a file another test wrote.
- Each test sets up its own data through fixtures, not through the UI: `fake_bank(...)` resets the fake bank and the app's stored data, and `fake_rates` / `fake_ollama` / `seed_categories` seed the rest.
- No fixed sleeps or `wait_for_timeout`. Wait on a condition: `expect(...)` assertions, or `page.wait_for_function(...)` when the UI animates (see `DashboardPage.expand`, which waits until no animation is running, so a box that is still sliding open can't move the scroll position mid-test).
- A test that passes alone but fails in parallel is waiting on the wrong thing: find what is still changing, don't add a sleep.

## Keep the suite lean

- Before writing, read the area's existing test file. Extend a test or add a case rather than adding a near-copy.
- One test per distinct behaviour: the happy path, each error the user sees, and the boundary that actually broke or could break. Skip permutations that run the same code path.
- A bug fix gets one regression test, written first and seen failing.
- Name tests as behaviour sentences: `test_new_user_sees_empty_state_prompting_bank_connection`.

## Before you finish

The Stop hook runs lint, type check and all tests when code changed. While iterating, run the tests you touched:

```bash
uv run pytest tests/unit/test_<module>.py
uv run pytest -m e2e tests/e2e/test_<feature>.py   # first time: uv run playwright install chromium
uv run pytest -m e2e -n auto                       # whole E2E suite, in parallel
```