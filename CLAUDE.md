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

**Phase 1 — Path A feasibility.** Before writing any custom backend, we are validating
whether TradingView's native Alpaca broker integration can fire orders directly from
a strategy script (not just manual orders).

**Do not start on Path B (custom webhook + bot) until Path A has been explicitly
ruled out.** The fastest possible answer to "does Path A work" is the most valuable
thing we can produce right now.

## Hard rules

1. **Paper account only** until Carlos gives an explicit go/no-go after Phase 3.
   `ALPACA_BASE_URL` must default to `https://paper-api.alpaca.markets`. Switching
   to live trading is a single env flag (`ALPACA_LIVE=true`) that must NOT default
   to true under any condition.
2. **No secrets in source.** API keys live in `.env` (gitignored) or in the deploy
   environment. If you find yourself about to paste a key into a file Claude Code
   is editing, stop.
3. **Every executed trade goes in the journal.** Timestamp, ticker, side, qty, fill
   price, signal source. This is how we reconcile against TradingView's Strategy
   Tester output (see spec §9.1, F6).
4. **Market orders only** for v1 entries and exits (spec §9.1, F4).
5. **Missing a signal is worse than executing late.** Reliability > latency
   (spec §9.4). Build retry logic, prefer idempotency, log everything.

## Architectural decisions made

- **Broker:** Alpaca (paper → live). Free, supports market orders + shorting on
  ETB stocks at $0 borrow fees, native TradingView integration, mature Python SDK.
- **Cadence:** Signal generation happens on 4-hour bar closes in TradingView. Our
  bot is event-driven (webhook in Path B), not polling. A 4-hour heartbeat job
  separately verifies liveness and position-state parity (spec §9.3).
- **Stack:** TBD — propose with reasoning before scaffolding. Constraints:
  must run as a long-lived service (for webhook receiver), must be cheap to host,
  must have a mature Alpaca client. Python + FastAPI is the obvious default
  unless there's a reason to choose otherwise.

## Coding conventions

- **Tests required** for any code that constructs an order, calculates position
  size, or interprets a signal. Mock the Alpaca client; do not hit the API in tests.
- **Type hints** on all functions that touch money, sides, or order types.
- **Explicit over implicit** for trading logic. No clever one-liners. The code
  should read like the spec.
- **Logs are structured** (JSON, key=value, or structlog). Carlos may grep them
  during incidents.

## Open questions blocking implementation

These are pulled from spec §11 and need answers from Carlos before the corresponding
code is written. Don't guess — ask Juan to get clarification:

- Whether v1 is single-ticker or watchlist (spec §11, Q9). Affects scheduler and
  capital allocation design.
- Notification channel and trigger (spec §11, Q8). Affects which client SDK to add.
- Restart behavior — skip stale signals or attempt late entry (spec §11, Q11).
  Affects webhook idempotency design.

## What NOT to do

- Don't reimplement the scoring logic (ADX buckets, MACD rules, regime zones, etc.).
  That's Carlos's domain in PineScript. Spec §5–§7 is reference, not a build list.
- Don't add stop-loss orchestration, partial position sizing, or pyramiding to v1
  (spec §2, Non-Goals).
- Don't build a UI in v1 unless explicitly asked. Carlos validates by reading
  Alpaca's dashboard + the trade journal.
- Don't optimize for low latency. Swing trading on 4-hour bars tolerates minutes
  of delay (spec §9.4).

## Reference

- Alpaca docs: https://docs.alpaca.markets/
- Alpaca Python SDK: https://github.com/alpacahq/alpaca-py
- TradingView ↔ Alpaca integration: https://alpaca.markets/tradingview
- Paper trading base URL: `https://paper-api.alpaca.markets`
