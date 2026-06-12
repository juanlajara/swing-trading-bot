import math
import threading

import pytest
from unittest.mock import MagicMock
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide, TimeInForce

from app.executor import execute_signal, _get_ticker_lock, _wait_for_flat, _wait_for_fill


def _make_404_api_error() -> APIError:
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_http_error = MagicMock()
    mock_http_error.response = mock_response
    return APIError({"message": "position does not exist"}, http_error=mock_http_error)


def _make_trading_client(
    equity: float = 200_000.0,
    order_id: str = "order-123",
    filled_avg_price: float = 100.0,
) -> MagicMock:
    client = MagicMock()
    client.get_account.return_value.equity = str(equity)
    order = MagicMock()
    order.id = order_id
    order.filled_avg_price = None
    client.submit_order.return_value = order
    client.get_orders.return_value = []
    # Simulate position clearing immediately after close
    client.get_open_position.side_effect = _make_404_api_error()
    # Simulate fill confirmation on first poll
    filled_order = MagicMock()
    filled_order.filled_avg_price = filled_avg_price
    client.get_order_by_id.return_value = filled_order
    return client


def _make_stock_data_client(symbol: str, price: float) -> MagicMock:
    client = MagicMock()
    client.get_stock_latest_trade.return_value = {symbol: MagicMock(price=price)}
    return client


def _make_crypto_data_client(symbol: str, price: float) -> MagicMock:
    client = MagicMock()
    client.get_crypto_latest_trade.return_value = {symbol: MagicMock(price=price)}
    return client


# equity=200_000, position_size_pct=0.02 → allocation=4_000
# price=100 → qty=40.0

def test_buy_closes_position_and_opens_long():
    trading = _make_trading_client(equity=200_000.0)
    data = _make_stock_data_client("NVDA", price=100.0)

    result = execute_signal("NVDA", "buy", trading, data)

    trading.close_position.assert_called_once_with("NVDA")
    req = trading.submit_order.call_args[0][0]
    assert req.side == OrderSide.BUY
    assert req.qty == pytest.approx(40.0)
    assert result["side"] == "buy"
    assert result["order_id"] == "order-123"


def test_sell_closes_position_and_opens_short():
    trading = _make_trading_client(equity=200_000.0)
    data = _make_stock_data_client("NVDA", price=100.0)

    result = execute_signal("NVDA", "sell", trading, data)

    trading.close_position.assert_called_once_with("NVDA")
    req = trading.submit_order.call_args[0][0]
    assert req.side == OrderSide.SELL
    assert req.qty == pytest.approx(40.0)
    assert result["side"] == "sell"


def test_no_existing_position_is_handled_gracefully():
    trading = _make_trading_client()
    trading.close_position.side_effect = _make_404_api_error()
    data = _make_stock_data_client("NVDA", price=100.0)

    result = execute_signal("NVDA", "buy", trading, data)

    trading.submit_order.assert_called_once()
    assert result["order_id"] == "order-123"


def test_non_404_api_error_is_reraised():
    trading = _make_trading_client()
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_http_error = MagicMock()
    mock_http_error.response = mock_response
    trading.close_position.side_effect = APIError({"message": "forbidden"}, http_error=mock_http_error)
    data = _make_stock_data_client("NVDA", price=100.0)

    with pytest.raises(APIError):
        execute_signal("NVDA", "buy", trading, data)


def test_equity_uses_day_time_in_force():
    trading = _make_trading_client()
    data = _make_stock_data_client("NVDA", price=100.0)

    execute_signal("NVDA", "buy", trading, data)

    req = trading.submit_order.call_args[0][0]
    assert req.time_in_force == TimeInForce.DAY


def test_crypto_uses_gtc_time_in_force():
    trading = _make_trading_client()
    data = _make_crypto_data_client("BTC/USD", price=50_000.0)

    execute_signal("BTC/USD", "buy", trading, data)

    req = trading.submit_order.call_args[0][0]
    assert req.time_in_force == TimeInForce.GTC


def test_buy_qty_allows_fractional():
    # allocation=4_000, price=30_000 → qty=0.1333...
    trading = _make_trading_client(equity=200_000.0)
    data = _make_crypto_data_client("BTC/USD", price=30_000.0)

    execute_signal("BTC/USD", "buy", trading, data)

    req = trading.submit_order.call_args[0][0]
    assert req.qty == pytest.approx(4_000.0 / 30_000.0, rel=1e-6)


def test_short_qty_is_floored_to_whole_shares():
    # allocation=4_000, price=150 → 4000/150=26.666... → floor=26
    trading = _make_trading_client(equity=200_000.0)
    data = _make_stock_data_client("NVDA", price=150.0)

    execute_signal("NVDA", "sell", trading, data)

    req = trading.submit_order.call_args[0][0]
    assert req.qty == 26
    assert req.qty == math.floor(4_000.0 / 150.0)


def test_waits_for_position_to_clear_before_new_order():
    trading = _make_trading_client()
    data = _make_stock_data_client("NVDA", price=100.0)

    execute_signal("NVDA", "sell", trading, data)

    # get_open_position must be called after close_position to confirm flat
    trading.get_open_position.assert_called_with("NVDA")


def test_open_orders_cancelled_before_close():
    trading = _make_trading_client()
    stale_order = MagicMock()
    stale_order.id = "stale-order-id"
    trading.get_orders.return_value = [stale_order]
    data = _make_stock_data_client("NVDA", price=100.0)

    execute_signal("NVDA", "sell", trading, data)

    trading.cancel_order_by_id.assert_called_once_with("stale-order-id")


def test_close_timeout_raises_without_cancelling_order():
    # Simulates after-hours: position never clears within timeout.
    # Close order must be left open so it fills at next market open.
    trading = _make_trading_client()
    trading.get_open_position.side_effect = None
    trading.get_open_position.return_value = MagicMock()  # always returns a position

    with pytest.raises(RuntimeError, match="did not fill"):
        _wait_for_flat("BOIL", trading, timeout=0)  # 0s timeout = expire immediately

    trading.cancel_order_by_id.assert_not_called()


def test_filled_avg_price_is_populated():
    trading = _make_trading_client(equity=200_000.0, filled_avg_price=98.50)
    data = _make_stock_data_client("NVDA", price=100.0)

    result = execute_signal("NVDA", "buy", trading, data)

    assert result["filled_avg_price"] == pytest.approx(98.50)


def test_filled_avg_price_is_none_when_fill_times_out():
    trading = _make_trading_client()
    unfilled_order = MagicMock()
    unfilled_order.filled_avg_price = None
    trading.get_order_by_id.return_value = unfilled_order

    result = _wait_for_fill("order-123", trading, timeout=0)

    assert result is None


def test_duplicate_signal_is_skipped():
    trading = _make_trading_client()
    data = _make_stock_data_client("AAPL", price=100.0)

    lock = _get_ticker_lock("AAPL")
    lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="duplicate signal"):
            execute_signal("AAPL", "buy", trading, data)
    finally:
        lock.release()
