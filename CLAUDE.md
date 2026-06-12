# Swing Trading Bot

## What this project is

A signal-to-order bridge that takes buy/sell signals from Carlos's existing TradingView
PineScript swing-trading strategy and routes them to an Alpaca brokerage account.
**Single user (Carlos), single broker (Alpaca), single trigger chart (4-hour).**

The strategy itself already exists and is validated in TradingView's Strategy Tester.
**We are NOT re-implementing the strategy.** We are building the executor around it.

Full requirements, glossary, backtest results, and open questions live in:

@docs/product_spec.md

## Current phase

**Phase 2b — Path B (custom bot) is live on Railway in paper mode.**

Path A (TradingView's native Alpaca broker integration) was ruled out — it cannot
fire strategy-script signals automatically. We are on Path B: TradingView sends
webhook alerts → Railway service receives them → Alpaca REST API executes orders.

## Hard rules

1. **Paper account only** until Carlos gives an explicit go/no-go after Phase 3.
   `ALPACA_BASE_URL` must default to `https://paper-api.alpaca.markets`. Switching
   to live trading is a single env flag (`ALPACA_LIVE=true`) that must NOT default
   to true under any condition.
2. **No secrets in source.** API keys live in `.env` (gitignored) or in Railway
   environment variables. If you find yourself about to paste a key into a file
   Claude Code is editing, stop.
3. **Every executed trade goes in the journal.** Timestamp, ticker, side, qty, fill
   price, signal source. This is how we reconcile against TradingView's Strategy
   Tester output (see spec §9.1, F6).
4. **Market orders only** for v1 entries and exits (spec §9.1, F4).
5. **Missing a signal is worse than executing late.** Reliability > latency
   (spec §9.4). Build retry logic, prefer idempotency, log everything.

## Architectural decisions made

### Integration path
- **Path A ruled out.** TradingView's native Alpaca connector only supports manual
  orders, not strategy-script signals. Path B (webhook bot) is the production path.

### Stack
- **Python + FastAPI + uvicorn.** Long-lived service, mature Alpaca SDK, cheap to host.
- **Deployment: Railway.** Nixpacks builder, `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
  Health check at `GET /health`, restart policy `ON_FAILURE` (max 10 retries).
- **Database: SQLite** (`trades.db`). Append-only trade journal. On Railway, mount a
  persistent volume at `/data` and set `DB_PATH=/data/trades.db` so the journal
  survives redeploys. Falls back to `trades.db` in the working directory for local dev.

### Position sizing
- `position_size_pct = 0.02` (2% of account equity per trade). This was set for a
  watchlist of ~50 tickers running concurrently; it is NOT 100% all-in per trade.
  The original spec assumed single-ticker 100%-in compounding — that model does not
  apply when multiple tickers are active simultaneously.

### Order execution logic (`app/executor.py`)
- **Signal flow:** cancel stale open orders → close existing position (ignore 404) →
  wait for flat → fetch latest price → submit market order for new direction.
- **Close-then-open, never reverse in one step.** Alpaca does not support atomic
  position reversal; two sequential orders are required.
- **Wait for flat before opening:** `_wait_for_flat` polls `get_open_position` for
  up to 15 seconds. On timeout (e.g. after-hours), it cancels the pending close
  order and raises — it does NOT proceed to open a new position. This prevents
  unintended position doubling.
- **After-hours behavior:** DAY orders don't fill after-hours. On timeout, the close
  order is left open to fill at the next market open — it is NOT cancelled. The new-direction
  entry is skipped; the next 4-hour bar signal re-triggers if the strategy still calls for it.
- **Fractional shorts are forbidden by Alpaca:** short-sell qty is `math.floor`'d
  to whole shares. Long (buy) qty allows fractional shares (rounded to 9 decimal places).
- **Crypto uses GTC time-in-force; stocks use DAY.** Crypto markets run 24/7 so
  DAY orders would never fill outside regular hours.
- **Per-ticker mutex (`_ticker_locks`):** duplicate concurrent webhooks for the same
  ticker are rejected immediately (`blocking=False` lock) to prevent race conditions.
- **Stale order cancellation:** before closing a position, all open orders for that
  symbol are cancelled to prevent wash-trade rejections on the new submission.

### Crypto support
- Supported symbols: `BTC/USD`, `ETH/USD`.
- TradingView sends `BTCUSD` / `ETHUSD` — normalized via `TICKER_ALIASES` in
  `app/config.py` before any Alpaca call.
- Crypto uses `CryptoHistoricalDataClient`; stocks use `StockHistoricalDataClient`.

### Webhook authentication
- Every webhook payload must include `"secret"` matching `WEBHOOK_SECRET` env var.
  Returns HTTP 401 otherwise. This is the only auth layer for the endpoint.

### Trade journal (`app/journal.py`)
- SQLite table `trades`: `id`, `ts` (UTC ISO-8601), `ticker`, `side`, `qty`,
  `order_id`, `filled_avg_price`, `signal_source` (default `tradingview_webhook`).
- Read via `GET /trades?secret=<WEBHOOK_SECRET>&limit=<n>` (default 100, most recent first).

### API endpoints
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `POST` | `/webhook` | `secret` field in body | Receive TradingView signal, execute trade |
| `GET`  | `/trades`  | `?secret=` query param | View trade journal |
| `GET`  | `/health`  | None | Liveness check for Railway |

### Environment variables
| Variable | Default | Notes |
|----------|---------|-------|
| `ALPACA_API_KEY` | — | Required |
| `ALPACA_SECRET_KEY` | — | Required |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Set in config but not used directly by alpaca-py (controlled by `ALPACA_LIVE`) |
| `ALPACA_LIVE` | `false` | Set to `true` to switch to live brokerage. **Never default true.** |
| `WEBHOOK_SECRET` | — | Required. Shared with TradingView alert URL |
| `POSITION_SIZE_PCT` | `0.02` | Fraction of equity per trade |
| `DB_PATH` | `trades.db` | Set to `/data/trades.db` on Railway persistent volume |

## Coding conventions

- **Tests required** for any code that constructs an order, calculates position
  size, or interprets a signal. Mock the Alpaca client; do not hit the API in tests.
- **Type hints** on all functions that touch money, sides, or order types.
- **Explicit over implicit** for trading logic. No clever one-liners. The code
  should read like the spec.
- **Logs are structured** (key=value format). Carlos may grep them during incidents.

## Open questions (unresolved)

- **Notifications (spec §11, Q8).** Should Carlos be alerted on every signal, or
  only on errors? Channel not yet decided (WhatsApp, email, SMS).
- **Reconciliation (spec §11, Q10).** How to handle material fill-price divergence
  from backtest — log only, halt, or alert?
- **Restart behavior (spec §11, Q11).** If the bot is down when a signal fires,
  skip or attempt late entry on restart?

## What NOT to do

- Don't reimplement the scoring logic (ADX buckets, MACD rules, regime zones, etc.).
  That's Carlos's domain in PineScript. Spec §5–§7 is reference, not a build list.
- Don't add stop-loss orchestration, partial position sizing, or pyramiding to v1
  (spec §2, Non-Goals).
- Don't build a UI in v1 unless explicitly asked. Carlos validates by reading
  Alpaca's dashboard + the trade journal (`GET /trades`).
- Don't optimize for low latency. Swing trading on 4-hour bars tolerates minutes
  of delay (spec §9.4).
- Don't change `ALPACA_LIVE` default to `true` under any circumstances.

## Reference

- Alpaca docs: https://docs.alpaca.markets/
- Alpaca Python SDK: https://github.com/alpacahq/alpaca-py
- TradingView ↔ Alpaca integration: https://alpaca.markets/tradingview
- Paper trading base URL: `https://paper-api.alpaca.markets`
- Railway deployment: https://railway.app
