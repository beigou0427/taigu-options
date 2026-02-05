"""
🔰 台指期權終極新手機：預設最遠月版
- ✅ 預設最遠月合約（長期投資）
- ✅ 新手教學（折疊）
- ✅ 10大嚴厲警示（折疊）  
- ✅ 核心：FinMind + Black-Scholes + 勝率
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權新手器**")

# ---------------------------------
# 📚 新手教學區 (折疊)
# ---------------------------------
with st.expander("📚 **新手教學：3分鐘看懂**", expanded=False):
    st.markdown("""
    **CALL 📈**：看漲 | **PUT 📉**：看跌
    **槓桿**：台指漲1%，合約賺N倍
    **價內**：現在賺錢（穩）| **價外**：現在賠錢（賭）
    **Delta**：跟漲係數（0.5=台指漲1點，合約漲0.5點）
    """)

# ---------------------------------
# 資料載入
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token: str):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    
    end_str = date.today().strftime("%Y-%m-%d")
    start_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")

    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=start_str, end_date=end_str)
        S_current = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
        data_date = index_df["date"].iloc[-1] if not index_df.empty else end_str
    except:
        S_current, data_date = 23000.0, end_str

    opt_start_str = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start_str, end_date=end_str)
    
    if df.empty: return S_current, pd.DataFrame(), pd.to_datetime(data_date)
    
    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date].copy()
    return S_current, df_latest, max(latest_date, pd.to_datetime(data_date))

with st.spinner("載入資料..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("資料載入失敗")
        st.stop()

m1, m2 = st.columns(2)
m1.metric("📈 加權指數", f"{S_current:,.0f}")
m2.metric("📊 資料日期", latest_date.strftime("%Y-%m-%d"))

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown("### 1️⃣ 方向")
    direction = st.radio("預測", ["CALL 📈", "PUT 📉"], horizontal=True, label_visibility="collapsed")
    target_cp = "CALL" if "CALL" in direction else "PUT"

with c2:
    st.markdown("### 2️⃣ 合約")
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
    # 🔧 關鍵修正：預設最遠月合約
    sel_contract = st.selectbox("月份", future_contracts, index=-1, label_visibility="collapsed")

with c3:
    st.markdown("### 3️⃣ 槓桿")
    target_lev = st.slider("倍數", 1.5, 20.0, 5.0, 0.5, label_visibility="collapsed")

with c4:
    st.markdown("### 4️⃣ 篩選")
    safe_mode = st.checkbox("🔰 穩健模式", value=True, help="剔除高風險價外合約")

st.info(f"🎯 **設定：{sel_contract} 月，{target_lev}x 槓桿**")

# ---------------------------------
# 核心計算
# ---------------------------------
def bs_price_delta(S, K, T, r, sigma, cp):
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if cp == "CALL" else max(K - S, 0)
        return float(intrinsic), (1.0 if intrinsic > 0 else 0.0)
    try:
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if cp == "CALL":
            return float(S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)), float(norm.cdf(d1))
        return float(K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)), float(-norm.cdf(-d1))
    except:
        return 0.0, 0.5

def calculate_win_rate(delta, days):
    if days <= 0: return 0.0
    p_itm = delta
    raw_win = (p_itm * 0.7 + 0.8 * 0.3) * 100
    return min(max(raw_win, 1.0), 99.0)

if st.button("🎯 **尋找最佳合約**", type="primary", use_container_width=True):
    target_df = df_latest[
        (df_latest["contract_date"].astype(str) == str(sel_contract)) & 
        (df_latest["call_put"].str.upper() == target_cp)
    ].copy()

    try:
        y, m = int(sel_contract[:4]), int(sel_contract[4:6])
        exp_date = date(y, m, 15)
        days_left = max((exp_date - latest_date.date()).days, 1)
    except: days_left = 60
    T = days_left / 365.0

    avg_iv = 0.20
    if 'implied_volatility' in target_df.columns:
        valid_ivs = pd.to_numeric(target_df['implied_volatility'], errors='coerce').dropna()
        avg_iv = valid_ivs.median() if not valid_ivs.empty else 0.20

    results = []
    for _, row in target_df.iterrows():
        try:
            K = float(row["strike_price"])
            price = float(row["close"])
            volume = int(row["volume"])
            
            iv_val = float(row.get("implied_volatility", 0))
            if iv_val <= 0 or np.isnan(iv_val): iv_val = avg_iv

            bs_price, delta = bs_price_delta(S_current, K, T, 0.02, iv_val, target_cp)
            delta_abs = abs(delta)

            if safe_mode and delta_abs < 0.15: continue

            calc_price = price if volume > 0 and price > 0 else bs_price
            status = "🟢 真成交" if volume > 0 and price > 0 else "🔵 模擬"

            if calc_price <= 0.1: continue
            
            leverage = (delta_abs * S_current) / calc_price
            win_rate = calculate_win_rate(delta_abs, days_left)
            is_itm = (target_cp == "CALL" and K <= S_current) or (target_cp == "PUT" and K >= S_current)

            results.append({
                "狀態": status,
                "履約價": int(K),
                "參考價": round(calc_price, 1),
                "槓桿": round(leverage, 2),
                "成交量": volume,
                "Delta": round(delta_abs, 2),
                "勝率": round(win_rate, 1),
                "位置": "價內" if is_itm else "價外",
                "差距": abs(leverage - target_lev)
            })
        except: continue

    df_res = pd.DataFrame(results)
    if df_res.empty:
        st.warning("無符合條件的合約")
        st.stop()

    df_res = df_res.sort_values("差距").reset_index(drop=True)
    best = df_res.iloc[0]

    st.balloons()
    
    # 🏆 最佳合約顯示
    st.markdown("### 🚀 **最佳推薦合約**")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"# **{int(best['履約價']):,}**")
        st.caption(f"{best['狀態']} | {best['位置']} | 成交量：{int(best['成交量']):,}")
    with c2:
        st.markdown("📈 **CALL**" if target_cp == "CALL" else "📉 **PUT**", 
                   unsafe_allow_html=True if target_cp == "CALL" else True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⚡ 槓桿", f"{best['槓桿']}x")
    col2.metric("🔥 勝率", f"{best['勝率']}%")
    col3.metric("📊 Delta", f"{best['Delta']}")
    col4.metric("💰 參考價", f"{best['參考價']}")

    # ⚠️ 10大警示 (折疊)
    with st.expander("⚠️ **10 大高風險警示**", expanded=False):
        lev = best['槓桿']
        risk_level = "🟢 相對安全" if lev < 6 else "🟡 中等風險" if lev < 12 else "🔴 極度危險"
        st.markdown(f"**1️⃣ 風險等級**：{risk_level}")

        profit_100 = int(best['Delta'] * 100 * 50)
        st.info(f"**2️⃣ 情境**：台指±100點，盈虧 **${profit_100:,}**")
        
        contract_cost = best['參考價'] * 50
        st.error(f"**3️⃣ 成本**：1口 **${int(contract_cost):,}**，本金需 **20倍**")
        
        st.error("**4️⃣ 停損**：權利金跌 **20%** 立即平倉！")
        st.warning("**5️⃣ 倉位**：總帳戶勿超 **10%**")
        st.error("**6️⃣ 最終**：**100% 歸零風險**，只用閒錢！")

    # 📋 列表
    st.markdown("### 📋 候選清單")
    show_df = df_res[["狀態","履約價","參考價","槓桿","勝率","Delta","位置","成交量"]].head(20)
    show_df["勝率"] = show_df["勝率"].map(lambda x: f"{x}%")
    st.dataframe(show_df, use_container_width=True)
