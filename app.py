import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import plotly.express as px
import numpy as np
from scipy.stats import norm
import requests

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")

st.markdown("# 🔥 **台指期權新手器**\n**免 FinMind！官方資料直接抓！**")

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
def get_txo_from_taifex(target_date=None):
    """直接從台灣期交所抓每日選擇權報表"""
    try:
        if target_date is None:
            target_date = date.today().strftime("%Y/%m/%d")
        url = f"https://www.taifex.com.tw/cht/3/optDailyMarketReport?queryDate={target_date}"
        tables = pd.read_html(url)
        df = tables[0]
        # 清理與命名統一化
        df = df.rename(columns={
            '契約': 'contract',
            '履約價': 'strike_price',
            '買方成交價': 'close',
            '買賣權': 'call_put'
        })
        df = df[df['contract'].astype(str).str.startswith('TXO', na=False)]
        df['contract_date'] = df['contract'].str.extract(r'TXO(\d{6})')
        df['call_put'] = df['call_put'].map({'買權': 'CALL', '賣權': 'PUT'})
        df = df[['contract_date', 'strike_price', 'close', 'call_put']]
        df = df.dropna(subset=['close'])
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        return df.dropna()
    except Exception as e:
        st.warning(f"載入資料錯誤: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_current_twii():
    """抓台指現價（Yahoo Finance）"""
    try:
        tx_data = yf.download('^TWII', period='5d', progress=False)
        return float(tx_data['Close'].dropna().iloc[-1])
    except:
        return 23000.0

with st.spinner("載入報價..."):
    S_current = get_current_twii()
    df_latest = get_txo_from_taifex()
    latest_date = date.today()

col1, col2 = st.columns(2)
col1.metric("📈 台指", f"{S_current:,.0f}")
col2.metric("📊 時間", latest_date.strftime('%Y-%m-%d'))

if df_latest.empty:
    st.error("⚠️ 無法取得資料，可能當日無交易或網站維護中。")
    st.stop()

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
st.markdown("## **🎮 操作超簡單！**")

col1, col2, col3 = st.columns(3)

# 左：策略選擇
with col1:
    st.markdown("### **玩法**")
    if st.button("🛡️ **長期**"):
        st.session_state.mode = 'long'
    if st.button("⚡ **短期**"):
        st.session_state.mode = 'short'

mode = st.session_state.get('mode', 'long')

# 中：月份選擇
with col2:
    st.markdown("### **月份**")
    all_contracts = sorted(df_latest['contract_date'].dropna().unique())
    sel_contract = st.selectbox("📅 選月份", all_contracts, index=0)

# 右：槓桿滑桿
with col3:
    st.markdown("### **槓桿**")
    if mode == 'long':
        target_lev = st.slider("穩穩賺", 1.5, 6.0, 2.5, 0.5)
    else:
        target_lev = st.slider("拚大錢", 5.0, 25.0, 12.0, 1.0)

st.info(f"🎯 **目標：{sel_contract} 月，{target_lev} 倍槓桿**")

# ---------------------------------
# 計算邏輯
# ---------------------------------
if st.button("🎯 **找最佳合約！**", use_container_width=True):
    df_sub = df_latest[df_latest['contract_date'].astype(str) == str(sel_contract)]
    if df_sub.empty:
        st.error("找不到該月份資料")
        st.stop()

    y, m = int(sel_contract[:4]), int(sel_contract[4:6])
    exp_date = date(y, m, 15)
    days_left = max((exp_date - date.today()).days, 1)
    T = days_left / 365.0

    def bs_delta(S, K, T, r, sigma, cp):
        try:
            d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
            return norm.cdf(d1) if cp == 'CALL' else -norm.cdf(-d1)
        except:
            return 0.5

    rows = []
    for _, row in df_sub.iterrows():
        K = float(row['strike_price'])
        price = float(row['close'])
        if price <= 0: continue
        cp = row['call_put']
        delta = bs_delta(S_current, K, T, 0.02, 0.25, cp)
        lev = abs(delta * S_current / price)
        rows.append({
            '類型': 'CALL 📈' if cp == 'CALL' else 'PUT 📉',
            '履約價': int(K),
            '權利金': round(price, 1),
            '槓桿': round(lev, 2),
            'Delta': round(abs(delta), 2),
            '成本': f"${int(price*50):,}",
            '價內': '✅' if (cp == 'CALL' and K <= S_current) or (cp == 'PUT' and K >= S_current) else '⚠️'
        })

    df_res = pd.DataFrame(rows)
    if df_res.empty:
        st.error("無有效合約")
        st.stop()

    df_res['差距'] = abs(df_res['槓桿'] - target_lev)
    df_res = df_res.sort_values('差距')
    best = df_res.iloc[0]

    st.balloons()
    st.markdown("## 🎉 **最佳合約！**")
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #d4edda, #c3e6cb); padding: 25px; 
                border-radius: 15px; border: 3px solid #28a745; text-align: center;'>
    <h1>🚀 **{best['履約價']:,}**</h1>
    <h2>⚡ **{best['槓桿']}x** (目標 {target_lev}x)</h2>
    <p><strong>{best['類型']} | {best['Delta']} Delta | {best['成本']}</strong></p>
    <h3>📋 下單指令：</h3>
    <code style='background: white; padding: 12px; border-radius: 8px; font-size: 18px;'>
    TXO {sel_contract} {best['類型'][:1]}{best['履約價']} 買進 1 口
    </code>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## 📋 **完整清單** (按槓桿排序)")
    st.dataframe(df_res[['類型','履約價','權利金','槓桿','Delta','成本','價內']].head(15),
                 use_container_width=True)

    st.markdown("## 📊 **槓桿分佈**")
    fig = px.scatter(df_res, x='履約價', y='槓桿', color='類型', size='Delta',
                     hover_data=['權利金'], title=f'{sel_contract} 槓桿圖')
    fig.add_hline(y=target_lev, line_dash="dash", line_color="red",
                  annotation_text=f"你的目標：{target_lev}x")
    st.plotly_chart(fig, use_container_width=True)

st.caption("⚠️ 資料來源：台灣期交所每日報表 | 僅供教學示範使用")
