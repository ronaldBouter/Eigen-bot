"""Test de strategie op historische data.

    python backtest.py --days 365
    python backtest.py --csv data.csv   (kolommen: ts,open,high,low,close,volume)
"""
import argparse

import pandas as pd

from config import CONFIG as cfg
from strategy import BUY, SELL, add_indicators, signal


def run(df: pd.DataFrame):
    df = add_indicators(df, cfg)
    eur, btc, entry, trades = cfg.paper_start_eur, 0.0, None, []
    for i in range(cfg.slow_sma + 1, len(df) + 1):
        window = df.iloc[:i]
        price = window["close"].iloc[-1]
        action, reason = signal(window, cfg, entry)
        if action == BUY:
            spend = eur * cfg.trade_fraction
            btc += spend * (1 - cfg.fee_pct) / price
            eur -= spend
            entry = price
        elif action == SELL:
            eur += btc * price * (1 - cfg.fee_pct)
            trades.append(price / entry * (1 - cfg.fee_pct) ** 2 - 1)
            btc, entry = 0.0, None

    first, last = df["close"].iloc[0], df["close"].iloc[-1]
    final = eur + btc * last
    wins = sum(t > 0 for t in trades)
    print(f"Periode:        {df.index[0]} → {df.index[-1]}")
    print(f"Startkapitaal:  €{cfg.paper_start_eur:,.2f}")
    print(f"Eindwaarde:     €{final:,.2f} ({final / cfg.paper_start_eur - 1:+.2%})")
    print(f"Buy & hold BTC: {last / first - 1:+.2%}")
    print(f"Trades:         {len(trades)} (gewonnen: {wins})")
    if trades:
        print(f"Gem. per trade: {sum(trades) / len(trades):+.2%} (na kosten)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--csv")
    args = p.parse_args()
    if args.csv:
        data = pd.read_csv(args.csv, parse_dates=["ts"], index_col="ts")
    else:
        from exchange import connect, fetch_history
        data = fetch_history(connect(cfg), cfg.symbol, cfg.timeframe, args.days)
    run(data)
