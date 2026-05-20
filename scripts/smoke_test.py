"""
Smoke test: verifies Alpaca paper-API connectivity and that secrets are loading.
Run with: python scripts/smoke_test.py
"""
import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()


def main() -> None:
    api_key = os.environ["ALPACA_API_KEY"]
    secret_key = os.environ["ALPACA_SECRET_KEY"]

    client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
    account = client.get_account()

    print(f"Account number: {account.account_number}")
    print(f"Buying power:   ${account.buying_power}")


if __name__ == "__main__":
    main()
