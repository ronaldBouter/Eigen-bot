# Bitcoin handelsrobot

Automatische aan- en verkoop van bitcoin via een exchange (standaard **Bitvavo**, maar elke exchange uit [ccxt](https://github.com/ccxt/ccxt) werkt, zoals Kraken of Binance).

> ⚠️ **Let op:** handelen in crypto is risicovol. Geen enkele strategie garandeert winst. Begin altijd met `MODE=paper` (nepgeld) en een backtest.

## Installatie

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # daarna .env aanpassen
```

## Gebruik

1. **Backtest**: test de strategie op historische koersen:
   ```bash
   python backtest.py --days 365
   ```
2. **Paper trading**: de bot draait live, maar met nepgeld (standaard €1000):
   ```bash
   python bot.py
   ```
   Het saldo en de trades komen in `state.json`, de log in `bot.log`.
3. **Live handelen**: maak op de exchange een API-sleutel aan met alleen rechten voor *handelen* (**nooit** voor opnemen/withdraw), zet die in `.env` met `MODE=live` en start `python bot.py`. De bot vraagt dan eerst om bevestiging.

## Strategie

| Regel | Standaard |
|---|---|
| **Kopen**: snelle SMA kruist boven de trage SMA *en* RSI < 70 | SMA 20 / 50 |
| **Verkopen**: snelle SMA kruist onder de trage SMA | |
| **Stop-loss**: verkopen bij verlies | 3% |
| **Take-profit**: verkopen bij winst | 6% |
| **Inzet per aankoop** | 25% van EUR-saldo |

Alle waarden zijn aan te passen in `.env`. De bot kijkt alleen naar **afgesloten** candles en controleert één keer per candle (standaard elk uur).

## Bestanden

- `bot.py`: de robot (paper- en live-modus)
- `strategy.py`: indicatoren en koop/verkoop-regels (hier pas je de strategie aan)
- `backtest.py`: strategie testen op historische data
- `exchange.py`: verbinding met de exchange via ccxt
- `config.py` / `.env`: instellingen
