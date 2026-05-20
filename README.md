# Swing Trading Bot

Signal-to-order bridge: receives TradingView webhook alerts on strategy signals and routes them to an Alpaca brokerage account.

**Paper trading only** until explicitly switched via `ALPACA_LIVE=true`.

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure secrets (never commit .env)
cp .env.example .env
# Edit .env and fill in your Alpaca paper API key and secret
```

## Smoke test

Verifies your API keys are correct and the paper account is reachable:

```bash
python scripts/smoke_test.py
```

Expected output:
```
Account number: PA...
Buying power:   $100000.00
```

## Run the server (development)

```bash
uvicorn app.main:app --reload
```

## Run tests

```bash
pytest
```

## Architecture

See `docs/product_spec.md` for the full spec. Summary:

- **Trigger:** TradingView fires a webhook alert on each 4-hour bar zero-cross.
- **Receiver:** FastAPI service receives the POST, validates the payload.
- **Executor:** Closes any existing position, opens the opposite side with 100% capital via market order.
- **Journal:** Every fill is logged to SQLite with timestamp, ticker, side, qty, fill price, signal source.
- **Broker:** Alpaca (paper → live via config flag).

## Config

| Var | Default | Notes |
|-----|---------|-------|
| `ALPACA_API_KEY` | required | Alpaca paper or live key |
| `ALPACA_SECRET_KEY` | required | Alpaca paper or live secret |
| `ALPACA_BASE_URL` | `https://paper-api.alpaca.markets` | Do not change until Phase 4 |
| `ALPACA_LIVE` | `false` | Never set to `true` without Carlos's explicit go/no-go |
