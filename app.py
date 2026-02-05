"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學 + 槓桿真篩選 + 月份自由選 + 只顯示真成交
- 硬編碼 TOKEN 版（本地/Cloud 通用）
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from FinMind.data import DataLoader
import plotly.express as px
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
# 資料載入（硬編碼 TOKEN）
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
        st.info("⚠️ TOKEN 過期？請去 https://finmindtrade.com 產生新 TOKEN 取代程式碼第 44 行")
        st.stop()
        return 23000, pd.DataFrame(), pd.Timestamp.now()

with st.spinner("載入報價..."):
    S_current, df_latest, latest_date = get_data()

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
# 計算（只秀真成交）
# ---------------------------------
if st.button("🎯 **找最佳合約！**", type="primary", use_container_width=True):
    
    target_df = df_latest[df_latest['contract_date'].astype(str) == str(sel_contract)]
    
    if target_df.empty:
        st.error(f"{sel_contract} 無資料")
        st.stop()
    
    # 到期日
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
        
        # 只顯示真成交！
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
            'Delta': round(delta_abs, 2),
            '成本': f"${int(price*50):,}",
            '價內': '✅' if (cp == 'CALL' and K <= S_current) or (cp == 'PUT' and K >= S_current) else '⚠️'
        })
    
    df_res = pd.DataFrame(results)
    if df_res.empty:
        st.warning("⚠️ 該月份無真成交合約，請試其他月份")
        st.stop()
    
    # 排序
    df_res['差距'] = abs(df_res['槓桿'] - target_lev)
    df_res = df_res.sort_values('差距')
    best = df_res.iloc[0]
    
    # 最佳推薦
    st.balloons()
    st.markdown("## 🎉 **最佳真成交合約！**")
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #d4edda, #c3e6cb); padding: 25px; 
                border-radius: 15px; border: 3px solid #28a745; text-align: center;'>
    <h1>🚀 **{best['履約價']:,}**</h1>
    <h2>⚡ **{best['槓桿']}x** (目標 {target_lev}x)</h2>
    <p><strong>{best['類型']} | {best['Delta']} Δ | {best['成交量']} 張 | {best['成本']}</strong></p>
    <h3>📋 下單指令：</h3>
    <code style='background: white; padding: 12px; border-radius: 8px; font-size: 18px;'>
    TXO {sel_contract} {best['類型'][:1]}{best['履約價']} 買進 1 口
    </code>
    </div>
    """, unsafe_allow_html=True)
    
    # 表格
    st.markdown("## 📋 **真成交清單** (按槓桿排序)")
    display_df = df_res[['類型','履約價','權利金','成交量','槓桿','Delta','成本','價內']].head(15)
    display_df['槓桿差距'] = df_res['差距'].head(15).round(2)
    st.dataframe(display_df, use_container_width=True)
    
    # 圖表
    st.markdown("## 📊 **真成交槓桿分佈**")
    fig = px.scatter(df_res, x='履約價', y='槓桿', color='類型', size='成交量',
                     hover_data=['權利金', '成交量'], title=f'{sel_contract} 真成交槓桿圖')
    fig.add_hline(y=target_lev, line_dash="dash", line_color="red", 
                  annotation_text=f"你的目標：{target_lev}x")
    st.plotly_chart(fig, use_container_width=True)

st.caption("⚠️ 期權有歸零風險，僅供學習 | 貝伊果屋出品 🔥")
