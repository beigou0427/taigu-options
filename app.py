"""
🔰 台指期權新手機：CALL 保證版
- CALL/PUT 分開推薦
- 遠月合約權利金門檻調低
- 新手介面完美
"""

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
from FinMind.data import DataLoader
import plotly.express as px
import numpy as np
from scipy.stats import norm

TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNCAwMTowNDowMyIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJlbWFpbCI6ImFzZDc4MzM1MjBAeWFob28uY29tLnR3IiwiaXAiOiIxLjE3Mi4xMDguNjkifQ.svsiG2FxPiuQPTsYgODId5uKXJ8imkWGORIgLKeFBpU"

st.set_page_config(page_title="台指期權新手機", layout="wide", page_icon="🔥")

st.markdown("# 🔥 **台指期權新手機**\n**CALL/PUT 都有！月份隨便選！**")

# 新手教學
with st.expander("📚 **新手教學**", expanded=False):
    st.markdown("""
    **CALL 📈** = 看好會漲 (付訂金買台指)
    **PUT 📉** = 怕會跌 (買保險)
    
    **長期**：2~3倍槓桿，選遠月，像用20%本金買台指
    **短期**：10~20倍槓桿，選近月，像買彩票
    """)

# 資料載入
@st.cache_data(ttl=300)
def get_data():
    tx_data = yf.download('^TWII', period='5d', progress=False)
    S_current = float(tx_data['Close'].dropna().iloc[-1])
    
    dl = DataLoader()
    dl.login_by_token(api_token=TOKEN)
    end_date = date.today().strftime('%Y-%m-%d')
    start_date = (date.today() - timedelta(days=60)).strftime('%Y-%m-%d')
    
    df = dl.taiwan_option_daily('TXO', start_date=start_date, end_date=end_date)
    df['date'] = pd.to_datetime(df['date'])
    latest_date = df['date'].max()
    df_latest = df[df['date'] == latest_date]
    
    return S_current, df_latest, latest_date

S_current, df_latest, latest_date = get_data()

col1.metric("📈 台指", f"{S_current:,.0f}")
col2.metric("📊 時間", latest_date.strftime('%Y-%m-%d'))

# 操作區
st.markdown("---")
col_btn, col_month, col_lev = st.columns(3)

# 策略按鈕
with col_btn:
    st.markdown("**玩法**")
    if st.button("🛡️ **長期**", type="primary" if st.session_state.get('mode', 'long') == 'long' else 'secondary'):
        st.session_state.mode = 'long'
    if st.button("⚡ **短期**", type="primary" if st.session_state.get('mode', 'long') == 'short' else 'secondary'):
        st.session_state.mode = 'short'

# 月份選擇
with col_month:
    st.markdown("**月份**")
    all_contracts = sorted(df_latest['contract_date'].unique())
    future_contracts = [c for c in all_contracts if str(c).isdigit() and int(str(c)) >= int(latest_date.strftime('%Y%m'))]
    sel_contract = st.selectbox("📅", future_contracts, index=min(3, len(future_contracts)-1))

# 槓桿滑桿
with col_lev:
    st.markdown("**槓桿**")
    mode = st.session_state.get('mode', 'long')
    if mode == 'long':
        target_lev = st.slider("穩賺", 1.5, 6.0, 2.5, 0.5)
    else:
        target_lev = st.slider("拚錢", 5.0, 25.0, 12.0, 1.0)

st.info(f"🎯 **{sel_contract} 月 | {target_lev}x 槓桿**")

# 搜尋按鈕
if st.button("🎯 **找合約！**", type="primary", use_container_width=True):
    
    target_df = df_latest[df_latest['contract_date'].astype(str) == str(sel_contract)]
    
    def bs_delta(S, K, T, r, sigma, cp):
        if T <= 0 or sigma <= 0: return 0.5
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
        return norm.cdf(d1) if cp == 'CALL' else -norm.cdf(-d1)
    
    results = []
    T = 0.25  # 假設 3 個月
    
    for _, row in target_df.iterrows():
        K = float(row['strike_price'])
        price = float(row['close'])
        cp = row['call_put']
        
        if price < 0.1: continue  # 降低門檻，確保 CALL 出現
        
        delta = bs_delta(S_current, K, T, 0.02, 0.25, cp)
        delta_abs = abs(delta)
        leverage = (delta_abs * S_current) / price
        
        results.append({
            '類型': 'CALL 📈' if cp == 'CALL' else 'PUT 📉',
            '履約價': int(K),
            '權利金': round(price, 1),
            '槓桿': round(leverage, 2),
            'Delta': round(delta_abs, 2),
            '成本': f"${int(price*50):,}",
            '價內': '✅' if (cp == 'CALL' and K <= S_current) or (cp == 'PUT' and K >= S_current) else '⚠️'
        })
    
    df_res = pd.DataFrame(results)
    df_res['差距'] = abs(df_res['槓桿'] - target_lev)
    df_res = df_res.sort_values('差距')
    
    # 分開 CALL / PUT
    df_call = df_res[df_res['類型'].str.contains('CALL')]
    df_put = df_res[df_res['類型'].str.contains('PUT')]
    
    st.balloons()
    
    # CALL 推薦
    if not df_call.empty:
        best_call = df_call.iloc[0]
        st.markdown("## 📈 **CALL 最佳推薦**")
        st.markdown(f"""
        <div style='background: #d4edda; padding: 20px; border-radius: 10px; border-left: 5px solid #28a745;'>
        <h2>🚀 **履約價：{best_call['履約價']:,}**</h2>
        <p>⚡ **槓桿：{best_call['槓桿']}x** | 💰 **{best_call['成本']}**</p>
        <code>TXO {sel_contract} C{best_call['履約價']} 買進 1 口</code>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("❌ 暫無 CALL 合約")
    
    # PUT 推薦
    if not df_put.empty:
        best_put = df_put.iloc[0]
        st.markdown("## 📉 **PUT 推薦**")
        st.markdown(f"""
        <div style='background: #f8d7da; padding: 20px; border-radius: 10px; border-left: 5px solid #dc3545;'>
        <h2>🛡️ **履約價：{best_put['履約價']:,}**</h2>
        <p>⚡ **槓桿：{best_put['槓桿']}x** | 💰 **{best_put['成本']}**</p>
        <code>TXO {sel_contract} P{best_put['履約價']} 買進 1 口</code>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("❌ 暫無 PUT 合約")
    
    # 完整清單
    if not df_res.empty:
        st.markdown("## 📋 **所有合約**")
        display_df = df_res[['類型','履約價','權利金','槓桿','Delta','成本','價內']].head(20)
        st.dataframe(display_df, use_container_width=True)
        
        # 圖表
        fig = px.scatter(df_res, x='履約價', y='槓桿', color='類型', size='Delta',
                        title=f'{sel_contract} 槓桿分佈')
        fig.add_hline(y=target_lev, line_color="red", line_dash="dash")
        st.plotly_chart(fig)

st.caption("⚠️ 期權有歸零風險")
