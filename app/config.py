from pydantic_settings import BaseSettings

WATCHLIST: list[str] = [
    "VOO", "GLD", "AAL", "NVDA", "JPM", "CAT", "NFLX", "TSLA", "TLT", "EEM",
    "GME", "COIN", "URA", "BTC/USD", "NKE", "ETH/USD", "PFE", "HD", "WMT", "RTX",
]
WATCHLIST_SET: set[str] = set(WATCHLIST)
WATCHLIST_SIZE: int = len(WATCHLIST)

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

    model_config = {"env_file": ".env"}


settings = Settings()
