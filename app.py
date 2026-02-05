"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學 + 槓桿真篩選 + 月份自由選 + 只顯示真成交
- 硬編碼 TOKEN 版（無分布圖）
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")

st.markdown("# 🔥 **台指期權新手器**\\n**月份隨便選！槓桿真篩選！只秀真成交！**")

# ---------------------------------
# 新手教學
# ---------------------------------
with st.expander("📚 **新手必看教學**", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        ### **選擇權超簡單**
        **CALL** 📈 = 看好會漲  
        **PUT** 📉 = 怕會大跌
        
        **槓桿 = 用 1 元控制 N 元台指**
        - 台指漲 1%，你賺槓桿 × 1%
        """)
    with col2:
        st.markdown("""
        ### **怎麼選？**
        | 🛡️ 長期 | ⚡ 短期 |
        |--------|--------|
        | 看好半年 | 賭這週 |
        | **2~3x** | **10~20x** |
        | **9月遠月** | **本週近月** |
        """)

# ---------------------------------
# 資料載入
# ---------------------------------
@st.cache_data(ttl=300)
def get_data():
    try:
        tx_data = yf.download('^TWII', period='5d', progress=False)
        S_current = float(tx_data['Close'].dropna().iloc[-1])
        
        # ★★★ 硬編碼 TOKEN（請用你的新 TOKEN 取代） ★★★
        TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNCAwMTowNDowMyIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJlbWFpbCI6ImFzZDc4MzM1MjBAeWFob28uY29tLnR3IiwiaXAiOiIxLjE3Mi4xMDguNjkifQ.svsiG2FxPiuQPTsYgODId5uKXJ8imkWGORIgLKeFBpU"
        
        dl = DataLoader()
        dl.login_by_token(api_token=TOKEN)
        end_date = date.today().strftime('%Y-%m-%d')
        start_date = (date.today() - timedelta(days=60)).strftime('%Y-%m-%d')
        
        df = dl.taiwan_option_daily('TXO', start_date=start_date, end_date=end_date)
        df['date'] = pd.to_datetime(df['date'])
        latest_date = df['date'].max()
        df_latest = df[df['date'] == latest_date]
        
        return S_current, df_latest, latest_date
    except Exception as e:
        st.error(f"資料載入失敗：{e}")
        st.info("⚠️ TOKEN 過期？請去 https://finmindtrade.com 產生新 TOKEN 取代程式碼第 52 行")
        st.stop()
        return 23000, pd.DataFrame(), pd.Timestamp.now()

with st.spinner("載入報價..."):
    S_current, df_latest, latest_date = get_data()

col1, col2 = st.columns(2)
col1.metric("📈 台指", f"{S_current:,.0f}")
col2.metric("📊 時間", latest_date.strftime('%Y-%m-%d'))

if df_latest.empty:
    st.error("無資料")
    st.stop()

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
st.markdown("## **🎮 操作超簡單！**")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### **玩法**")
    if st.button("🛡️ **長期**", type="primary" if st.session_state.get('mode', 'long') == 'long' else 'secondary'):
        st.session_state.mode = 'long'
    if st.button("⚡ **短期**", type="primary" if st.session_state.get('mode', 'long') == 'short' else 'secondary'):
        st.session_state.mode = 'short'

with col2:
    st.markdown("### **月份**")
    all_contracts = sorted(df_latest['contract_date'].unique())
    future_contracts = [c for c in all_contracts if str(c).isdigit() and int(str(c)) >= int(latest_date.strftime('%Y%m'))]
    sel_contract = st.selectbox("📅 選月份", future_contracts, 
                               index=len(future_contracts)-3 if len(future_contracts)>3 else 0)

with col3:
    st.markdown("### **槓桿**")
    mode = st.session_state.get('mode', 'long')
    if mode == 'long':
        target_lev = st.slider("穩穩賺", 1.5, 6.0, 2.5, 0.5)
    else:
        target_lev = st.slider("拚大錢", 5.0, 25.0, 12.0, 1.0)

st.info(f"🎯 **目標：{sel_contract} 月，{target_lev} 倍槓桿，只秀真成交！**")

# ---------------------------------
# 計算（無圖表版）
# ---------------------------------
if st.button("🎯 **找最佳合約！**", type="primary", use_container_width=True):
    
    target_df = df_latest[df_latest['contract_date'].astype(str) == str(sel_contract)]
    
    if target_df.empty:
        st.error(f"{sel_contract} 無資料")
        st.stop()
    
    try:
        y, m = int(sel_contract[:4]), int(sel_contract[4:6])
        exp_date = date(y, m, 15)
        days_left = max((exp_date - date.today()).days, 1)
    except:
        days_left = 30
    
    T = days_left / 365.0
    
    def bs_delta(S, K, T, r, sigma, cp):
        if T <= 0 or sigma <= 0: return 0.5
        try:
            d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
            if cp == 'CALL':
                return norm.cdf(d1)
            return -norm.cdf(-d1)
        except:
            return 0.5
    
    results = []
    for _, row in target_df.iterrows():
        K = float(row['strike_price'])
        price = float(row['close'])
        volume = int(row['volume'])
        
        if price < 1 or volume == 0:
            continue
            
        cp = row['call_put']
        delta = bs_delta(S_current, K, T, 0.02, 0.25, cp)
        delta_abs = abs(delta)
        leverage = (delta_abs * S_current) / price
        
        results.append({
            '類型': 'CALL 📈' if cp == 'CALL' else 'PUT 📉',
            '履約價': int(K),
            '權利金': round(price, 1),
            '成交量': f"{volume:,}",
            '槓桿': round(leverage, 2),
            'Delta': round(delta_abs, 2
