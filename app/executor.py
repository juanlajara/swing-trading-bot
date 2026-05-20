from __future__ import annotations
import logging
from typing import Literal

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from app.config import CRYPTO_SYMBOLS, WATCHLIST_SIZE

logger = logging.getLogger(__name__)

Action = Literal["buy", "sell"]


def _get_latest_price(symbol: str, data_client) -> float:
    if symbol in CRYPTO_SYMBOLS:
        from alpaca.data.requests import CryptoLatestTradeRequest
        resp = data_client.get_crypto_latest_trade(
            CryptoLatestTradeRequest(symbol_or_symbols=symbol)
        )
    else:
        from alpaca.data.requests import StockLatestTradeRequest
        resp = data_client.get_stock_latest_trade(
            StockLatestTradeRequest(symbol_or_symbols=symbol)
        )
    return float(resp[symbol].price)


def execute_signal(
    symbol: str,
    action: Action,
    trading_client: TradingClient,
    data_client,
) -> dict:
    account = trading_client.get_account()
    allocation = float(account.equity) / WATCHLIST_SIZE

    try:
        trading_client.close_position(symbol)
        logger.info("closed_position symbol=%s", symbol)
    except APIError as exc:
        if exc.status_code != 404:
            raise
        logger.info("no_open_position symbol=%s", symbol)

    price = _get_latest_price(symbol, data_client)
    qty = round(allocation / price, 9)
    side = OrderSide.BUY if action == "buy" else OrderSide.SELL
    tif = TimeInForce.GTC if symbol in CRYPTO_SYMBOLS else TimeInForce.DAY

    order = trading_client.submit_order(
        MarketOrderRequest(symbol=symbol, qty=qty, side=side, time_in_force=tif)
    )

    logger.info("order_submitted symbol=%s side=%s qty=%s order_id=%s", symbol, action, qty, order.id)

    return {
        "order_id": str(order.id),
        "symbol": symbol,
        "side": action,
        "qty": qty,
        "filled_avg_price": getattr(order, "filled_avg_price", None),
    }
