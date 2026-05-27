from pydantic_settings import BaseSettings

CRYPTO_SYMBOLS: set[str] = {"BTC/USD", "ETH/USD"}

# TradingView may send crypto as "BTCUSD" — normalize to Alpaca's format
TICKER_ALIASES: dict[str, str] = {
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
}


class Settings(BaseSettings):
    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_live: bool = False
    webhook_secret: str
    position_size_pct: float = 0.02  # fraction of equity per trade (default 2% for ~50 tickers)

    model_config = {"env_file": ".env"}


settings = Settings()
