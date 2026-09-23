import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _f(name, default):
    return float(os.getenv(name, default))


@dataclass(frozen=True)
class Config:
    exchange: str = os.getenv("EXCHANGE", "bitvavo")
    api_key: str = os.getenv("API_KEY", "")
    api_secret: str = os.getenv("API_SECRET", "")
    symbol: str = os.getenv("SYMBOL", "BTC/EUR")
    timeframe: str = os.getenv("TIMEFRAME", "1h")
    mode: str = os.getenv("MODE", "paper").lower()
    paper_start_eur: float = _f("PAPER_START_EUR", 1000)
    fast_sma: int = int(_f("FAST_SMA", 20))
    slow_sma: int = int(_f("SLOW_SMA", 50))
    rsi_period: int = int(_f("RSI_PERIOD", 14))
    rsi_max_buy: float = _f("RSI_MAX_BUY", 70)
    trade_fraction: float = _f("TRADE_FRACTION", 0.25)
    stop_loss_pct: float = _f("STOP_LOSS_PCT", 0.03)
    take_profit_pct: float = _f("TAKE_PROFIT_PCT", 0.06)
    fee_pct: float = _f("FEE_PCT", 0.0025)


CONFIG = Config()
