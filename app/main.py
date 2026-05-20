import logging
from contextlib import asynccontextmanager

from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient
from alpaca.trading.client import TradingClient
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.config import CRYPTO_SYMBOLS, TICKER_ALIASES, WATCHLIST_SET, settings
from app.executor import execute_signal
from app.journal import init_db, log_trade

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


@app.post("/webhook")
def webhook(payload: WebhookPayload) -> dict:
    if payload.secret != settings.webhook_secret:
        raise HTTPException(status_code=401, detail="invalid secret")

    ticker = TICKER_ALIASES.get(payload.ticker.upper(), payload.ticker.upper())
    if ticker not in WATCHLIST_SET:
        raise HTTPException(status_code=400, detail=f"{ticker} not in watchlist")

    action = payload.action.lower()
    if action not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail=f"invalid action: {action}")

    data_client = _crypto_data_client if ticker in CRYPTO_SYMBOLS else _stock_data_client
    result = execute_signal(ticker, action, _trading_client, data_client)

    log_trade(
        ticker=ticker,
        side=action,
        qty=result["qty"],
        order_id=result["order_id"],
        filled_avg_price=result.get("filled_avg_price"),
    )

    logger.info("webhook_processed ticker=%s action=%s order_id=%s", ticker, action, result["order_id"])
    return result


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
