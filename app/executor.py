from __future__ import annotations

import logging
import math
import threading
import time
from typing import Literal

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from app.config import CRYPTO_SYMBOLS, settings

logger = logging.getLogger(__name__)

Action = Literal["buy", "sell"]

# Prevents duplicate concurrent webhooks for the same ticker from racing each other
_ticker_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_ticker_lock(symbol: str) -> threading.Lock:
    with _locks_mutex:
        if symbol not in _ticker_locks:
            _ticker_locks[symbol] = threading.Lock()
        return _ticker_locks[symbol]


def _cancel_open_orders(symbol: str, trading_client: TradingClient) -> None:
    try:
        open_orders = trading_client.get_orders(
            filter=GetOrdersRequest(symbols=[symbol], status=QueryOrderStatus.OPEN)
        )
        for order in open_orders:
            try:
                trading_client.cancel_order_by_id(order.id)
                logger.info("cancelled_order symbol=%s order_id=%s", symbol, order.id)
            except APIError:
                pass
    except APIError:
        pass


def _wait_for_flat(symbol: str, trading_client: TradingClient, timeout: int = 15) -> None:
    """Poll until position is closed or timeout. Prevents shorting into a pending close order."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            trading_client.get_open_position(symbol)
        except APIError as exc:
            if exc.status_code == 404:
                return
            raise
        time.sleep(0.5)
    logger.warning("position_close_timeout symbol=%s", symbol)


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
    lock = _get_ticker_lock(symbol)
    if not lock.acquire(blocking=False):
        raise RuntimeError(f"duplicate signal already in flight for {symbol}, skipping")
    try:
        return _execute(symbol, action, trading_client, data_client)
    finally:
        lock.release()


def _execute(
    symbol: str,
    action: Action,
    trading_client: TradingClient,
    data_client,
) -> dict:
    account = trading_client.get_account()
    allocation = float(account.equity) * settings.position_size_pct

    # Cancel any stale open orders first to avoid wash-trade rejections
    _cancel_open_orders(symbol, trading_client)

    try:
        trading_client.close_position(symbol)
        logger.info("closed_position symbol=%s", symbol)
        # Wait for the close to fill before opening the new direction
        _wait_for_flat(symbol, trading_client)
    except APIError as exc:
        if exc.status_code != 404:
            raise
        logger.info("no_open_position symbol=%s", symbol)

    price = _get_latest_price(symbol, data_client)
    side = OrderSide.BUY if action == "buy" else OrderSide.SELL

    # Alpaca rejects fractional short sells — floor to whole shares
    if side == OrderSide.SELL:
        qty = math.floor(allocation / price)
        if qty == 0:
            raise ValueError(
                f"allocation ${allocation:.2f} too small to short {symbol} at ${price:.2f}"
            )
    else:
        qty = round(allocation / price, 9)

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
