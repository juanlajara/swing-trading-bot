import pytest
from unittest.mock import MagicMock
from alpaca.common.exceptions import APIError
from alpaca.trading.enums import OrderSide, TimeInForce

from app.executor import execute_signal


def _make_404_api_error() -> APIError:
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_http_error = MagicMock()
    mock_http_error.response = mock_response
    return APIError({"message": "position does not exist"}, http_error=mock_http_error)


def _make_trading_client(equity: float = 200_000.0, order_id: str = "order-123") -> MagicMock:
    client = MagicMock()
    client.get_account.return_value.equity = str(equity)
    order = MagicMock()
    order.id = order_id
    order.filled_avg_price = None
    client.submit_order.return_value = order
    return client


def _make_stock_data_client(symbol: str, price: float) -> MagicMock:
    client = MagicMock()
    client.get_stock_latest_trade.return_value = {symbol: MagicMock(price=price)}
    return client


def _make_crypto_data_client(symbol: str, price: float) -> MagicMock:
    client = MagicMock()
    client.get_crypto_latest_trade.return_value = {symbol: MagicMock(price=price)}
    return client


# equity=200_000, watchlist_size=20 → allocation=10_000
# price=100 → qty=100.0

def test_buy_closes_position_and_opens_long():
    trading = _make_trading_client(equity=200_000.0)
    data = _make_stock_data_client("NVDA", price=100.0)

    result = execute_signal("NVDA", "buy", trading, data)

    trading.close_position.assert_called_once_with("NVDA")
    req = trading.submit_order.call_args[0][0]
    assert req.side == OrderSide.BUY
    assert req.qty == pytest.approx(100.0)
    assert result["side"] == "buy"
    assert result["order_id"] == "order-123"


def test_sell_closes_position_and_opens_short():
    trading = _make_trading_client(equity=200_000.0)
    data = _make_stock_data_client("NVDA", price=100.0)

    result = execute_signal("NVDA", "sell", trading, data)

    trading.close_position.assert_called_once_with("NVDA")
    req = trading.submit_order.call_args[0][0]
    assert req.side == OrderSide.SELL
    assert req.qty == pytest.approx(100.0)
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


def test_fractional_qty_not_floored():
    # allocation=10_000, price=30_000 → qty=0.3333...
    trading = _make_trading_client(equity=200_000.0)
    data = _make_crypto_data_client("BTC/USD", price=30_000.0)

    execute_signal("BTC/USD", "buy", trading, data)

    req = trading.submit_order.call_args[0][0]
    assert req.qty == pytest.approx(10_000.0 / 30_000.0, rel=1e-6)
