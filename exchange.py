import ccxt
import pandas as pd


def connect(cfg, private: bool = False):
    params = {"enableRateLimit": True}
    if private:
        params |= {"apiKey": cfg.api_key, "secret": cfg.api_secret}
    return getattr(ccxt, cfg.exchange)(params)


def fetch_candles(ex, symbol, timeframe, limit=200, since=None) -> pd.DataFrame:
    rows = ex.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.set_index("ts")


def fetch_history(ex, symbol, timeframe, days) -> pd.DataFrame:
    """Haalt meerdere pagina's historische candles op."""
    ms = ex.parse_timeframe(timeframe) * 1000
    since = ex.milliseconds() - days * 86_400_000
    frames = []
    while since < ex.milliseconds() - ms:
        df = fetch_candles(ex, symbol, timeframe, limit=1000, since=since)
        if df.empty:
            break
        frames.append(df)
        since = int(df.index[-1].timestamp() * 1000) + ms
    out = pd.concat(frames)
    return out[~out.index.duplicated()]
