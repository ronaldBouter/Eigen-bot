"""Handelsstrategie: SMA-crossover met RSI-filter en stop-loss / take-profit."""
from __future__ import annotations

import pandas as pd

BUY, SELL, HOLD = "BUY", "SELL", "HOLD"


def add_indicators(df: pd.DataFrame, cfg) -> pd.DataFrame:
    df = df.copy()
    df["sma_fast"] = df["close"].rolling(cfg.fast_sma).mean()
    df["sma_slow"] = df["close"].rolling(cfg.slow_sma).mean()
    delta = df["close"].diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / cfg.rsi_period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / cfg.rsi_period, adjust=False).mean()
    df["rsi"] = 100 - 100 / (1 + gain / loss)
    return df


def signal(df: pd.DataFrame, cfg, entry_price: float | None) -> tuple[str, str]:
    """Geeft (actie, reden) op basis van de laatste afgesloten candle.

    entry_price is de aankoopprijs van de open positie, of None als er geen positie is.
    """
    if len(df) < cfg.slow_sma + 1:
        return HOLD, "te weinig data"
    prev, last = df.iloc[-2], df.iloc[-1]
    price = last["close"]

    if entry_price is not None:
        change = price / entry_price - 1
        if change <= -cfg.stop_loss_pct:
            return SELL, f"stop-loss ({change:+.2%})"
        if change >= cfg.take_profit_pct:
            return SELL, f"take-profit ({change:+.2%})"
        if prev["sma_fast"] >= prev["sma_slow"] and last["sma_fast"] < last["sma_slow"]:
            return SELL, "trend omlaag (SMA-kruising)"
        return HOLD, f"positie open ({change:+.2%})"

    crossed_up = prev["sma_fast"] <= prev["sma_slow"] and last["sma_fast"] > last["sma_slow"]
    if crossed_up and last["rsi"] < cfg.rsi_max_buy:
        return BUY, f"trend omhoog (SMA-kruising, RSI {last['rsi']:.0f})"
    return HOLD, "geen signaal"
