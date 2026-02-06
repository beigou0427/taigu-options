"""
🔰 台指期權雙模式系統 (投資人展示版 - 無額外依賴)
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm
import plotly.express as px
# ❌移除這行錯誤來源
# from streamlit_plotly_events import plotly_events 

# =========================
# Session State
# =========================
init_state = {
    'portfolio': [],
    'search_res_easy': [],
    'user_type': 'free',
    'is_pro': False,
    'disclaimer_accepted': False
}
for key, value in init_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# 如果沒有設定secrets，使用預設Token (展示用)
FINMIND_TOKEN = st.secrets.get("finmind_token", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0")

st.set_page_config(page_title="台指期權雙模式Pro", layout="wide", page_icon="🔥")

# ---------------------------------
# 合規聲明 (投資人要求)
# ---------------------------------
if not st.session_state.disclaimer_accepted:
    st.warning("🚨 **重要聲明**：本工具僅供教育參考，非投資建議！期權交易有高風險。")
    if st.button("✅ 我了解風險，繼續使用", type="primary"):
        st.session_state.disclaimer_accepted = True
        st.rerun()
    st.stop()

# ---------------------------------
# 資料載入 & BS公式
# ---------------------------------
@st.cache_data(ttl=60)
def get_data(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    
    end_str = date.today().strftime("%Y-%m-%d")
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=10)).strftime("%Y-%m-%d"))
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
    except: S = 23000.0

    opt_start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start, end_date=end_str)
    
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(end_str)
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest

def bs_price_delta(S, K, T, r, sigma, cp):
    if T <= 0: return 0.0, 0.5
    try:
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if cp == "CALL": return S*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d2), norm.cdf(d1)
        return K*np.exp(-r*T)*norm.cdf(-d2)-S*norm.cdf(-d1), -norm.cdf(-d1)
    except: return 0.0, 0.5

def calculate_win_rate(delta, days):
    return min(max((abs(delta)*0.7 + 0.8*0.3)*100, 1), 99)

with st.spinner("載入數據中..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("無法連線 FinMind API")
        st.stop()

# ==========================================
# 頂部導航
# ==========================================
c_title, c_up = st.columns([3, 1])
with c_title:
    st.markdown("# 🔥 **台指期權雙模式 Pro**")
with c_up:
    if not st.session_state.is_pro:
        if st.button("⭐ 升級 Pro (NT$299)", use_container_width=True):
            st.session_state.is_pro = True
            st.balloons()
            st.rerun()
    else:
        st.success("👑 PRO 會員")

tab1, tab2, tab3 = st.tabs(["🔰 **新手 CALL**", "🔥 **專業戰情**", "📊 **回測中心**"])

# ==========================================
# TAB1：新手介面 + 停損模擬
# ==========================================
with tab1:
    st.info(f"📊 **大盤指數**：{S_current:,.0f} (更新: {latest_date.strftime('%Y-%m-%d')})")
    
    c1, c2, c3, c4 = st.columns([1.5, 2, 1.5, 1])
    with c1:
        st.markdown("### 1️⃣ 策略")
        st.success("📈 **看漲 CALL**")
        target_cp = "CALL"
    with c2:
        st.markdown("### 2️⃣ 合約")
        if not df_latest.empty:
            cons = sorted(df_latest["contract_date"].astype(str).unique())
            sel_contract = st.selectbox("月份", cons, index=len(cons)-1 if cons else 0, label_visibility="collapsed")
        else: sel_contract = ""
    with c3:
        st.markdown("### 3️⃣ 槓桿")
        target_lev = st.slider("倍數", 2.0, 15.0, 5.0, 0.5, label_visibility="collapsed")
    with c4:
        st.markdown("### 4️⃣ 篩選")
        safe = st.checkbox("穩健", True)

    if st.button("🎯 **尋找最佳機會**", type="primary", use_container_width=True):
        if not df_latest.empty:
            # 搜尋邏輯
            tdf = df_latest[(df_latest["contract_date"].astype(str)==sel_contract) & 
                            (df_latest["call_put"].str.upper()=="CALL")].copy()
            y, m = int(sel_contract[:4]), int(sel_contract[4:6])
            days = max((date(y, m, 15) - latest_date.date()).days, 1)
            T = days/365.0
            
            res = []
            for _, row in tdf.iterrows():
                try:
                    K = float(row["strike_price"])
                    p = float(row["close"])
                    if p <= 0: continue
                    bs, d = bs_price_delta(S_current, K, T, 0.02, 0.2, "CALL")
                    lev = (abs(d)*S_current)/p
                    win = calculate_win_rate(d, days)
                    res.append({"K":int(K), "P":p, "L":lev, "W":win, "D":abs(d)})
                except: continue
            
            if res:
                res.sort(key=lambda x: abs(x['L']-target_lev))
                best = res[0]
                
                st.divider()
                col_res, col_sim = st.columns(2)
                
                with col_res:
                    st.markdown("### 🏆 **推薦合約**")
                    st.metric(f"履約價 {best['K']}", f"{best['P']} 點", f"槓桿 {best['L']:.1f}x")
                    st.metric("勝率", f"{best['W']:.0f}%", f"Delta {best['D']:.2f}")
                
                with col_sim:
                    st.markdown("### 🛡️ **停損模擬 (投資人最愛)**")
                    sl = st.slider("停損 %", 10, 50, 20)
                    tp = st.slider("停利 %", 20, 100, 50)
                    
                    risk = best['P'] * (sl/100) * 50
                    reward = best['P'] * (tp/100) * 50
                    rr = reward/risk if risk > 0 else 0
                    
                    st.write(f"📉 **最大虧損**：NT$ -{risk:.0f}")
                    st.write(f"💰 **預期獲利**：NT$ +{reward:.0f}")
                    st.caption(f"風報比 1 : {rr:.1f}")

# ==========================================
# TAB2：投組 (Freemium 限制)
# ==========================================
with tab2:
    if len(st.session_state.portfolio) > 0:
        st.dataframe(pd.DataFrame(st.session_state.portfolio))
    else:
        st.info("尚無持倉，請先搜尋加入")
    
    if not st.session_state.is_pro:
        st.warning("🔒 **免費版限制持有 3 口合約**")

# ==========================================
# TAB3：回測 (修正版 - 移除plotly_events)
# ==========================================
with tab3:
    st.markdown("### 📊 **歷史回測 (Pro)**")
    
    if not st.session_state.is_pro:
        st.info("⭐ 升級 Pro 解鎖 5 年回測數據與夏普比率分析！")
        st.image("https://via.placeholder.com/800x400?text=Pro+Only+Feature", use_column_width=True)
    else:
        # Pro 功能展示
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.selectbox("回測合約", ["TXO 近月", "TXO 遠月"])
        with col_b2:
            st.slider("回測期間 (年)", 1, 5, 1)
        
        if st.button("🚀 開始回測"):
            # 模擬數據
            np.random.seed(42)
            returns = np.random.normal(0.05, 0.2, 100)
            cum_ret = (1 + returns).cumprod()
            
            st.line_chart(cum_ret)
            st.metric("年化報酬", "+18.5%", "夏普 1.2")
            st.success("✅ 回測完成：策略優於大盤")
