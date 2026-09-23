"""Bitcoin handelsrobot. Start met: python bot.py  (standaard paper trading)."""
import json
import logging
import time
from pathlib import Path

from config import CONFIG as cfg
from exchange import connect, fetch_candles
from strategy import BUY, SELL, add_indicators, signal

STATE_FILE = Path("state.json")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")],
)
log = logging.getLogger("bot")


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"eur": cfg.paper_start_eur, "btc": 0.0, "entry_price": None, "trades": []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


class PaperBroker:
    """Simuleert orders met nepgeld; saldo staat in state.json."""

    def __init__(self, state):
        self.state = state

    def buy(self, price):
        spend = self.state["eur"] * cfg.trade_fraction
        btc = spend * (1 - cfg.fee_pct) / price
        self.state["eur"] -= spend
        self.state["btc"] += btc
        return btc

    def sell(self, price):
        btc = self.state["btc"]
        self.state["eur"] += btc * price * (1 - cfg.fee_pct)
        self.state["btc"] = 0.0
        return btc


class LiveBroker:
    """Plaatst echte market-orders op de exchange."""

    def __init__(self, ex):
        self.ex = ex
        self.base, self.quote = cfg.symbol.split("/")

    def buy(self, price):
        spend = self.ex.fetch_balance()["free"].get(self.quote, 0) * cfg.trade_fraction
        if self.ex.has.get("createMarketBuyOrderWithCost"):
            order = self.ex.create_market_buy_order_with_cost(cfg.symbol, spend)
        else:
            amount = float(self.ex.amount_to_precision(cfg.symbol, spend / price))
            order = self.ex.create_market_buy_order(cfg.symbol, amount)
        return order.get("filled") or order.get("amount")

    def sell(self, price):
        free = self.ex.fetch_balance()["free"].get(self.base, 0)
        amount = float(self.ex.amount_to_precision(cfg.symbol, free))
        order = self.ex.create_market_sell_order(cfg.symbol, amount)
        return order.get("filled") or amount


def main():
    live = cfg.mode == "live"
    if live:
        if not (cfg.api_key and cfg.api_secret):
            raise SystemExit("MODE=live vereist API_KEY en API_SECRET in .env")
        if input("LIVE modus: er wordt met ECHT geld gehandeld. Typ JA om door te gaan: ") != "JA":
            raise SystemExit("Afgebroken.")

    ex = connect(cfg, private=live)
    ex.load_markets()
    state = load_state()
    broker = LiveBroker(ex) if live else PaperBroker(state)
    interval = ex.parse_timeframe(cfg.timeframe)
    log.info("Gestart: %s %s %s, modus=%s", cfg.exchange, cfg.symbol, cfg.timeframe, cfg.mode)

    while True:
        try:
            df = fetch_candles(ex, cfg.symbol, cfg.timeframe, limit=cfg.slow_sma + 100)
            df = add_indicators(df.iloc[:-1], cfg)  # laatste candle is nog niet afgesloten
            price = df["close"].iloc[-1]
            action, reason = signal(df, cfg, state["entry_price"])

            if action == BUY:
                qty = broker.buy(price)
                state["entry_price"] = price
                log.info("KOOP %.8f BTC @ %.2f — %s", qty, price, reason)
            elif action == SELL:
                qty = broker.sell(price)
                pnl = price / state["entry_price"] - 1
                state["entry_price"] = None
                log.info("VERKOOP %.8f BTC @ %.2f (%+.2f%%) — %s", qty, price, pnl * 100, reason)
            else:
                log.info("Prijs %.2f — %s", price, reason)

            if action != "HOLD":
                state["trades"].append({"time": str(df.index[-1]), "action": action,
                                        "price": price, "reason": reason})
            if not live:
                value = state["eur"] + state["btc"] * price
                log.info("Paper saldo: €%.2f + %.8f BTC = €%.2f", state["eur"], state["btc"], value)
            save_state(state)
        except Exception:
            log.exception("Fout in de lus; opnieuw proberen bij volgende ronde")

        # wacht tot net na het sluiten van de volgende candle
        time.sleep(interval - time.time() % interval + 5)


if __name__ == "__main__":
    main()
