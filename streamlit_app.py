# Long/Short Radar (Binance Futures)
# pip install streamlit requests pandas numpy

import datetime as dt
import numpy as np
import pandas as pd
import requests
import streamlit as st

BINANCE = "https://fapi.binance.com/futures/data"
SYMS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT"]

st.set_page_config(page_title="Long/Short Radar", layout="wide")
st.title("Long/Short Radar (Binance Futures)")

sym = st.selectbox("Sembol", SYMS, index=0)
tf_choice = st.radio("Zaman Penceresi", ["12h","24h","1w","1mo"], horizontal=True)

def since_dt(window: str) -> pd.Timestamp:
    hours = {"12h":12, "24h":24, "1w":7*24, "1mo":30*24}[window]
    return pd.Timestamp.utcnow() - pd.Timedelta(hours=hours)

@st.cache_data(show_spinner=False, ttl=60)
def fetch_ratio(endpoint: str, symbol: str) -> pd.DataFrame:
    """Fetch 5m long/short ratio data from Binance futures endpoint."""
    params = {"symbol": symbol, "period": "5m", "limit": 1000}
    url = f"{BINANCE}/{endpoint}"
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    if df.empty:
        return df
    # Ensure correct dtypes
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    if "longShortRatio" in df.columns:
        df["ratio"] = pd.to_numeric(df["longShortRatio"], errors="coerce").astype(float)
        df["long_pct"] = df["ratio"]/(1+df["ratio"])
        df["short_pct"] = 1 - df["long_pct"]
    return df.dropna(subset=["timestamp","long_pct","short_pct"])

tabs = st.tabs(["Tüm Hesaplar","Top Trader (Hesap)","Top Trader (Pozisyon)"])
endpoints = ["globalLongShortAccountRatio","topLongShortAccountRatio","topLongShortPositionRatio"]
labels = {
    "globalLongShortAccountRatio":"Tüm Hesaplar",
    "topLongShortAccountRatio":"Top Trader (Hesap)",
    "topLongShortPositionRatio":"Top Trader (Pozisyon)",
}

summaries = []
cutoff = since_dt(tf_choice)

for i, ep in enumerate(endpoints):
    with tabs[i]:
        try:
            df = fetch_ratio(ep, sym)
        except Exception as e:
            st.error(f"Veri çekme hatası: {e}")
            continue

        if df.empty:
            st.warning("Veri yok.")
            continue

        df = df[df["timestamp"] >= cutoff].sort_values("timestamp")
        if df.empty:
            st.warning("Seçili zaman penceresi için veri bulunamadı.")
            continue

        # Ağırlıklı ortalama: medyan + EMA karması
        long_med = float(df["long_pct"].median())
        span = max(2, round(len(df)/3))
        long_ema = float(df["long_pct"].ewm(span=span).mean().iloc[-1])
        long_pct = (long_med + long_ema) / 2.0
        short_pct = 1.0 - long_pct

        dom = "LONG baskın" if long_pct > 0.53 else ("SHORT baskın" if long_pct < 0.47 else "Nötr")
        st.metric("Dominance", dom, delta=f"Long %{long_pct*100:.1f} / Short %{short_pct*100:.1f}")
        st.line_chart(df.set_index("timestamp")[["long_pct","short_pct"]])

        summaries.append((ep, long_pct, short_pct, dom))

st.subheader("Özet")
for name, lp, sp, dom in summaries:
    st.write(f"**{labels[name]}** – {dom} (Long %{lp*100:.1f} / Short %{sp*100:.1f})")

st.caption("Not: %53 üstü LONG, %47 altı SHORT baskın kabul edilmiştir; aralık Nötr sayılır.")
