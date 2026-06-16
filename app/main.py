import asyncio
import logging
from contextlib import asynccontextmanager

from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import CRYPTO_SYMBOLS, TICKER_ALIASES, settings
from app.executor import execute_signal
from app.journal import init_db, log_trade, get_trades

logger = logging.getLogger(__name__)

_trading_client = TradingClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
    paper=not settings.alpaca_live,
)
_stock_data_client = StockHistoricalDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
)
_crypto_data_client = CryptoHistoricalDataClient(
    api_key=settings.alpaca_api_key,
    secret_key=settings.alpaca_secret_key,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="swing-trading-bot", lifespan=lifespan)


class WebhookPayload(BaseModel):
    ticker: str
    action: str
    secret: str


def _process_signal(ticker: str, action: str) -> None:
    data_client = _crypto_data_client if ticker in CRYPTO_SYMBOLS else _stock_data_client
    try:
        result = execute_signal(ticker, action, _trading_client, data_client)
    except Exception as exc:
        logger.error("execute_signal_failed ticker=%s action=%s error=%s", ticker, action, exc)
        return
    log_trade(
        ticker=ticker,
        side=action,
        qty=result["qty"],
        order_id=result["order_id"],
        filled_avg_price=result.get("filled_avg_price"),
    )
    logger.info("webhook_processed ticker=%s action=%s order_id=%s", ticker, action, result["order_id"])


@app.post("/webhook")
async def webhook(payload: WebhookPayload) -> dict:
    logger.info("webhook_received ticker=%s action=%s", payload.ticker, payload.action)

    if payload.secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="invalid secret")

    ticker = TICKER_ALIASES.get(payload.ticker.upper(), payload.ticker.upper())
    action = payload.action.lower()
    if action not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail=f"invalid action: {action}")

    # Return 200 immediately — TradingView times out webhooks after ~3 seconds,
    # but order execution (close + wait for flat + open) can take up to 25 seconds.
    # Processing runs in the default thread pool so the event loop stays unblocked.
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _process_signal, ticker, action)

    logger.info("webhook_queued ticker=%s action=%s", ticker, action)
    return {"status": "queued", "ticker": ticker, "action": action}


@app.get("/trades")
def trades(secret: str, limit: int = 100) -> list:
    if secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="invalid secret")
    return get_trades(limit=limit)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
