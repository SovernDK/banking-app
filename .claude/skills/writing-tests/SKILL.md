---
name: writing-tests
description: Use when writing or updating tests in tests/, adding coverage for new code, or fixing a bug that needs a regression test. Covers this repo's end-to-end test style, shared fakes and naming.
---

# Writing tests

Test end to end: enter through the highest public entry point and fake only the system boundaries. A test proves a behaviour the user (or calling system) sees, not how the code gets there.

## Framework and layout

- **Unit:** pytest, in `tests/unit/test_<module>.py`. Enter through the public function or the FastAPI app via `fastapi.testclient.TestClient(app)` (from `app.main`).
- **E2E:** Playwright via pytest-playwright, in `tests/e2e/test_<feature>.py`, every file marked `pytestmark = pytest.mark.e2e`. The session-scoped `base_url` fixture in `tests/e2e/conftest.py` starts the real app with uvicorn on a free port; tests use the `page` fixture and relative URLs.
- **Page objects:** `tests/e2e/pages/<page>_page.py`; select by role, label or `data-testid`, assert with `playwright.sync_api.expect` (auto-waits).
- Shared fixtures go in the nearest `conftest.py`; reuse or generalize an existing fixture before adding one.
- Use `pytest.mark.parametrize` for input/expected tables, not copy-pasted tests.

## What every test file must cover

1. The documented happy path
2. Every error path: thrown errors, rejected promises, error returns
3. Boundary inputs: empty arrays, zero, negative numbers, unicode strings
4. If fixing a bug: write the failing regression test FIRST, then the fix

## Naming

- `it` strings state behavior, not implementation:
  "rejects invoices with a negative total", never "works correctly"
- Regression tests cite the issue: "handles empty line items (#482)"

## Mocking policy

- Mock at system boundaries only: network, filesystem, clock, randomness
- NEVER mock the module under test or its pure helpers
- Use fake timers for time-dependent code; never sleep in a test
- Restore all mocks in afterEach

## Keep the suite lean

- Before writing, read the area's existing test file. Extend a test or add a case rather than adding a near-copy.
- One test per distinct behaviour: the happy path, each error the user sees, and the boundary that actually broke or could break. Skip permutations that run the same code path.
- A bug fix gets one regression test, written first and seen failing.
- Name tests as behaviour sentences: `test_new_user_sees_empty_state_prompting_bank_connection`.

## Before you finish

Run and make sure all pass:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest            # unit
uv run pytest -m e2e     # E2E (first time: uv run playwright install chromium)
```