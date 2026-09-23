"""Dashboard voor de bitcoin-bot. Start met: streamlit run app.py"""
import dataclasses
import json
import os
import shutil
import signal as sig
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backtest import simulate
from config import CONFIG
from exchange import connect, fetch_candles, fetch_history
from strategy import add_indicators

HERE = Path(__file__).parent
STATE_FILE = HERE / "state.json"
LOG_FILE = HERE / "bot.log"
PID_FILE = HERE / "bot.pid"

st.set_page_config(page_title="Bitcoin Bot", page_icon="₿", layout="wide")


# ---------- bot-proces ----------

def bot_pid():
    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, 0)
        return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        PID_FILE.unlink(missing_ok=True)
        return None


def start_bot():
    cmd = [sys.executable, "bot.py"]
    if shutil.which("caffeinate"):  # macOS: voorkom slaapstand zolang de bot draait
        cmd = ["caffeinate", "-i", *cmd]
    proc = subprocess.Popen(cmd, cwd=HERE, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PID_FILE.write_text(str(proc.pid))


def stop_bot(pid):
    try:
        os.killpg(pid, sig.SIGTERM)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)


# ---------- data ----------

@st.cache_resource
def exchange():
    ex = connect(CONFIG)
    ex.load_markets()
    return ex


@st.cache_data(ttl=60, show_spinner=False)
def recent_candles(timeframe):
    df = fetch_candles(exchange(), CONFIG.symbol, timeframe, limit=CONFIG.slow_sma + 200)
    return add_indicators(df, CONFIG)


@st.cache_data(ttl=3600, show_spinner="Historische koersen ophalen…")
def history(timeframe, days):
    return fetch_history(exchange(), CONFIG.symbol, timeframe, days)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def price_chart(df, orders, height=420):
    fig = go.Figure()
    fig.add_scatter(x=df.index, y=df["close"], name="Koers", line=dict(width=1.5))
    fig.add_scatter(x=df.index, y=df["sma_fast"], name="SMA snel", line=dict(width=1, dash="dot"))
    fig.add_scatter(x=df.index, y=df["sma_slow"], name="SMA traag", line=dict(width=1, dash="dash"))
    orders = orders[orders["time"] >= df.index[0]] if not orders.empty else orders
    if not orders.empty:
        for action, color, symbol in (("BUY", "#16a34a", "triangle-up"), ("SELL", "#dc2626", "triangle-down")):
            o = orders[orders["action"] == action]
            fig.add_scatter(x=o["time"], y=o["price"], mode="markers",
                            name="Koop" if action == "BUY" else "Verkoop",
                            marker=dict(color=color, symbol=symbol, size=11),
                            text=o["reason"], hovertemplate="%{text}<br>€%{y:,.0f}<extra></extra>")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.08), hovermode="x unified")
    return fig


# ---------- pagina ----------

st.title("₿ Bitcoin Bot")
tab_live, tab_backtest, tab_log = st.tabs(["Live", "Backtest", "Logboek"])

with tab_live:
    @st.fragment(run_every="60s")
    def live():
        pid = bot_pid()
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.markdown(f"**Status:** {'🟢 draait' if pid else '⚪ gestopt'} · "
                    f"modus **{CONFIG.mode}** · {CONFIG.symbol} · {CONFIG.timeframe}")
        if pid:
            if c2.button("⏹ Stop bot", width="stretch"):
                stop_bot(pid)
                st.rerun()
        elif CONFIG.mode == "live":
            c2.warning("Live-modus start je alleen via de terminal.")
        elif c2.button("▶ Start bot", type="primary", width="stretch"):
            start_bot()
            st.rerun()
        if not pid and STATE_FILE.exists() and c3.button("↺ Paper-saldo resetten", width="stretch"):
            STATE_FILE.unlink()
            st.rerun()

        try:
            df = recent_candles(CONFIG.timeframe)
            price = df["close"].iloc[-1]
        except Exception as e:
            st.error(f"Kan koers niet ophalen: {e}")
            return

        state = load_state()
        m = st.columns(4)
        m[0].metric("BTC-koers", f"€{price:,.0f}",
                    f"{price / df['close'].iloc[-25] - 1:+.2%} (24 candles)" if len(df) > 25 else None)
        if state:
            value = state["eur"] + state["btc"] * price
            m[1].metric("Waarde (paper)", f"€{value:,.2f}",
                        f"{value / CONFIG.paper_start_eur - 1:+.2%}")
            m[2].metric("EUR / BTC", f"€{state['eur']:,.2f}", f"{state['btc']:.6f} BTC", delta_color="off")
            entry = state.get("entry_price")
            m[3].metric("Open positie", f"€{entry:,.0f}" if entry else "geen",
                        f"{price / entry - 1:+.2%}" if entry else None)
            orders = pd.DataFrame(state["trades"], columns=["time", "action", "price", "reason"])
            orders["time"] = pd.to_datetime(orders["time"])
        else:
            m[1].metric("Waarde (paper)", f"€{CONFIG.paper_start_eur:,.2f}")
            m[2].caption("Nog geen trades. Start de bot om te beginnen.")
            orders = pd.DataFrame(columns=["time", "action", "price", "reason"])

        st.plotly_chart(price_chart(df, orders), width="stretch")
        if not orders.empty:
            st.subheader("Trades")
            table = orders.iloc[::-1].assign(
                time=orders["time"].dt.tz_convert("Europe/Amsterdam").dt.strftime("%d-%m-%Y %H:%M"),
                action=orders["action"].map({"BUY": "🟢 Koop", "SELL": "🔴 Verkoop"}))
            st.dataframe(table, hide_index=True, width="stretch",
                         column_config={"time": "Tijd", "action": "Actie", "reason": "Reden",
                                        "price": st.column_config.NumberColumn("Prijs", format="€%.0f")})
        st.caption("Ververst elke minuut automatisch.")

    live()

with tab_backtest:
    st.caption("Test instellingen op koersen uit het verleden. Er wordt niet echt gehandeld.")
    a, b, c = st.columns(3)
    timeframe = a.selectbox("Timeframe", ["1h", "4h", "1d"],
                            index=["1h", "4h", "1d"].index(CONFIG.timeframe) if CONFIG.timeframe in ("1h", "4h", "1d") else 0)
    days = a.slider("Periode (dagen)", 30, 1095, 365, step=30)
    fast = b.slider("SMA snel", 5, 100, CONFIG.fast_sma)
    slow = b.slider("SMA traag", 10, 250, CONFIG.slow_sma)
    stop = c.slider("Stop-loss %", 1.0, 20.0, CONFIG.stop_loss_pct * 100, 0.5)
    take = c.slider("Take-profit %", 1.0, 50.0, CONFIG.take_profit_pct * 100, 0.5)
    frac = a.slider("Inzet per aankoop %", 5, 100, int(CONFIG.trade_fraction * 100), 5)

    if fast >= slow:
        st.warning("SMA snel moet kleiner zijn dan SMA traag.")
    elif st.button("Backtest draaien", type="primary"):
        cfg = dataclasses.replace(CONFIG, timeframe=timeframe, fast_sma=fast, slow_sma=slow,
                                  stop_loss_pct=stop / 100, take_profit_pct=take / 100,
                                  trade_fraction=frac / 100)
        try:
            data = history(timeframe, days)
        except Exception as e:
            st.error(f"Kan historische koersen niet ophalen: {e}")
            st.stop()
        with st.spinner("Rekenen…"):
            r = simulate(data, cfg)
        trades = r["trades"]
        m = st.columns(4)
        m[0].metric("Eindwaarde", f"€{r['final']:,.2f}", f"{r['return']:+.2%}")
        m[1].metric("Buy & hold", f"{r['buy_hold']:+.2%}")
        m[2].metric("Trades", len(trades), f"{sum(t > 0 for t in trades)} gewonnen", delta_color="off")
        m[3].metric("Gem. per trade (na kosten)", f"{sum(trades) / len(trades):+.2%}" if trades else "–")

        eq = pd.DataFrame({"Bot": r["equity"],
                           "Buy & hold": r["df"]["close"] / r["df"]["close"].iloc[0] * r["start"]}).dropna()
        st.subheader("Waarde van €%d" % r["start"])
        st.line_chart(eq, height=280)
        st.subheader("Koers en trades")
        st.plotly_chart(price_chart(r["df"], r["orders"]), width="stretch")

with tab_log:
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(errors="replace").splitlines()[-200:]
        st.code("\n".join(reversed(lines)), language=None)
    else:
        st.info("Nog geen logboek. Start de bot eerst.")
