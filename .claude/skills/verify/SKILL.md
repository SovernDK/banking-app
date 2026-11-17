---
name: verify
description: Launch Yiji against the fake Enable Banking server and drive it in a real browser to verify a change at runtime.
---

# Verifying Yiji at runtime

No real bank or rates service needed: `tests/fakes/enable_banking.py` and `tests/fakes/exchange_rates.py` are full stand-ins, configurable over HTTP.

## Launch (mirrors tests/e2e/conftest.py)

```bash
# fake bank and fake ECB rates
uv run python -m uvicorn tests.fakes.enable_banking:create_fake_enable_banking --factory --port $BANK_PORT
uv run python -m uvicorn tests.fakes.exchange_rates:create_fake_exchange_rates --factory --port $RATES_PORT
# test RSA key
uv run python -c "from app.tls import *; from pathlib import Path; write_private_key(generate_private_key(), Path('$KEY'))"
# the app — call uvicorn directly (python -m app runs check_local_callback and reads .env defaults)
YIJI_PORT=$APP_PORT YIJI_DATA_DIR=$DATA YIJI_ENABLE_BANKING_ENVIRONMENT=sandbox \
YIJI_ENABLE_BANKING_API_URL=http://127.0.0.1:$BANK_PORT \
YIJI_EXCHANGE_RATES_API_URL=http://127.0.0.1:$RATES_PORT \
YIJI_ENABLE_BANKING_SANDBOX_REDIRECT_URL=http://127.0.0.1:$APP_PORT/callback \
ENABLE_BANKING_SANDBOX_ID=verify ENABLE_BANKING_SANDBOX_KEY_PATH=$KEY \
uv run python -m uvicorn app.main:app --port $APP_PORT
```

Health: app `/api/health`, fake bank `/docs`. Use a fresh `YIJI_DATA_DIR` — never the real `.yiji/`.

## Drive (Playwright, `uv run python script.py`)

- Seed/flip the bank: `POST /_fake/configure` with `transactions`, `accounts`, `deny_access`, `session_expired`, `failure_status`. Each call **replaces** the whole config (resets transactions).
- Seed rates: `POST /_fake/configure` on the rates fake with `{"rates": daily(first, last, PLN="4.3", ...)}` (helper in `tests/fakes/exchange_rates.py`) or `failure_status`.
- Flows: `/` → `connect-bank` button → fake `/auth` redirects to callback → back to `/` with `spending-chart` + `total` test ids.
- Force a refetch: set `synced_at` to null in `$DATA/bank.json` (otherwise refetched only after 720 min); history lives in `$DATA/yiji.sqlite3`.
- Run the daily sync once: same env as the app, `uv run python -m app.sync` (exit 0/1/2).
- Period query values are `week` / `month` (not `last_week`).
- Hosted relay page: serve `site/` with `python -m http.server`, point the sandbox redirect URL at `http://127.0.0.1:$SITE_PORT/callback.html`; the full connect flow then goes app → site → `/api/bank/callback`.

## Gotchas

- ECharts animates: wait ~2s before screenshotting the chart, or bars look missing.
- `echarts` is not a window global — inspect the chart via screenshots, not `page.evaluate`.
- macOS has no `timeout`; for `python -m app` startup checks use `perl -e 'alarm 8; exec @ARGV' uv run python -m app`.
