import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(layout="wide")
st.markdown("## 🔥 台指期權（Yahoo Finance 版）")

# 加權指數即時
@st.cache_data(ttl=30)
def get_twx():
    ticker = yf.Ticker("^TWII")
    return ticker.fast_info['last_price']

twx_price = get_twx()
st.metric("加權指數", f"{twx_price:,.0f}")

# TXO 合約清單（真實代碼）
txo_contracts = {
    "2024/6月 價平 Call": "TXOC240623250",
    "2024/6月 價內 Call": "TXOC240623240",
    "2024/6月 價外 Call": "TXOC240623260",
    "2024/6月 價平 Put": "TXOP240623250",
}

selected = st.selectbox("📋 選擇真實合約", list(txo_contracts.keys()))

symbol = txo_contracts[selected]
st.info(f"**Yahoo 代碼**：`{symbol}`")

# 抓即時期權報價
@st.cache_data(ttl=60)
def get_txo_quote(symbol):
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        hist = ticker.history(period="1d")
        
        if hist.empty:
            return None
            
        return {
            "last_price": hist['Close'].iloc[-1],
            "volume": hist['Volume'].iloc[-1],
            "bid": info.get('bid', 'N/A'),
            "ask": info.get('ask', 'N/A'),
            "change": info.get('regularMarketChangePercent', 'N/A')
        }
    except:
        return None

quote = get_txo_quote(symbol)

if quote:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("權利金", f"{quote['last_price']:.2f}")
    with col2:
        st.metric("成交量", f"{int(quote['volume']):,}")
    with col3:
        st.metric("買價", quote['bid'])
    with col4:
        st.metric("漲跌", f"{quote['change']:.1f}%")
    
    # 估槓桿（Delta 粗估）
    delta_est = 0.5  # 價平假設
    leverage = (delta_est * twx_price) / quote['last_price']
    st.metric("估槓桿", f"{leverage:.1f}x")
    
    st.caption(f"更新：{datetime.now().strftime('%H:%M:%S')} | Yahoo Finance")
else:
    st.error(f"❌ 找不到 `{symbol}`\n\n檢查代碼或市況無交易")

# 批量抓多個合約
if st.button("📊 抓 12 個熱門合約"):
    symbols = [
        "TXOC240623240", "TXOC240623250", "TXOC240623260",
        "TXOP240623240", "TXOP240623250", "TXOP240623260"
    ]
    
    results = []
    for sym in symbols:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="1d")
        if not hist.empty:
            results.append({
                '代碼': sym,
                '權利金': hist['Close'].iloc[-1],
                '成交量': int(hist['Volume'].iloc[-1]),
                '槓桿': (0.5 * twx_price) / hist['Close'].iloc[-1]
            })
    
    df = pd.DataFrame(results)
    st.dataframe(df.sort_values('槓桿', ascending=False))
    
    fig = px.scatter(df, x='權利金', y='槓桿', size='成交量', 
                    hover_name='代碼', title="12檔 TXO 真實報價")
    st.plotly_chart(fig)
