from __future__ import annotations
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# On Railway, mount a persistent volume at /data and set DB_PATH=/data/trades.db.
# Falls back to local trades.db for development.
DB_PATH = Path(os.environ.get("DB_PATH", "trades.db"))
logger = logging.getLogger(__name__)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ts               TEXT    NOT NULL,
                ticker           TEXT    NOT NULL,
                side             TEXT    NOT NULL,
                qty              REAL    NOT NULL,
                order_id         TEXT    NOT NULL,
                filled_avg_price REAL,
                signal_source    TEXT    NOT NULL DEFAULT 'tradingview_webhook'
            )
        """)


def log_trade(
    ticker: str,
    side: str,
    qty: float,
    order_id: str,
    filled_avg_price: float | None = None,
    signal_source: str = "tradingview_webhook",
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO trades (ts, ticker, side, qty, order_id, filled_avg_price, signal_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, ticker, side, qty, order_id, filled_avg_price, signal_source),
        )
    logger.info("trade_logged ticker=%s side=%s qty=%s order_id=%s", ticker, side, qty, order_id)


def get_trades(limit: int = 100) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]
