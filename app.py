"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學 + 槓桿真篩選 + 月份自由選
- 只顯示真成交（volume > 0）
- CALL / PUT 分開篩選（超清晰！）
- 全 FinMind 版（無 YF）
- 新 TOKEN (2026-02-05)
- 新增：Black-Scholes 理論價格參考
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

# =========================
# 新 TOKEN (已更新 2026-02-05)
# =========================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權新手器**\n**月份隨便選！槓桿真篩選！只秀真成交！**")

# ---------------------------------
# 新手教學
# ---------------------------------
with st.expander("📚 **新手必看教學**", expanded=True):
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            """
### **選擇權超簡單**
**CALL** 📈 = 看好會漲  
**PUT** 📉 = 怕會大跌

**槓桿 = 用 1 元控制 N 元台指**
- 台指漲 1%，你賺槓桿 × 1%
"""
        )
    with col_b:
        st.markdown(
            """
### **怎麼選？**
| 🛡️ 長期 | ⚡ 短期 |
|--------|--------|
| 看好半年 | 賭這週 |
| **2~3x** | **10~20x** |
| **遠月** | **近月** |
"""
        )

# ---------------------------------
# 資料載入 (全 FinMind)
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token: str):
    if not token:
        raise ValueError("FINMIND_TOKEN 尚未設定")

    dl = DataLoader()
    dl.login_by_token(api_token=token)

    end_str = date.today().strftime("%Y-%m-%d")
    start_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")

    # 1. 抓大盤指數 (TAIEX)
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=start_str, end_date=end_str)
        if not index_df.empty:
            S_current = float(index_df["close"].iloc[-1])
            data_date = index_df["date"].iloc[-1]
        else:
            futures_df = dl.taiwan_futures_daily("TX", start_date=start_str, end_date=end_str)
            if not futures_df.empty:
                S_current = float(futures_df["close"].iloc[-1])
                data_date = futures_df["date"].iloc[-1]
            else:
                S_current = 31800.0  # fallback
                data_date = end_str
    except:
        S_current = 31800.0
        data_date = end_str

    # 2. 抓期權資料 (TXO)
    opt_start_str = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start_str, end_date=end_str)
    
    if df.empty:
        return S_current, pd.DataFrame(), pd.to_datetime(data_date)
        
    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date].copy()

    if latest_date > pd.to_datetime(data_date):
        display_date = latest_date
    else:
        display_date = pd.to_datetime(data_date)

    return S_current, df_latest, display_date


with st.spinner("載入 FinMind 資料..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except Exception as e:
        st.error(f"資料載入失敗：{e}")
        st.stop()

m1, m2 = st.columns(2)
m1.metric("📈 加權指數", f"{S_current:,.0f}")
m2.metric("📊 資料日期", latest_date.strftime("%Y-%m-%d"))

if df_latest.empty:
    st.error("目前無期權資料")
    st.stop()

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
st.markdown("## **🎮 操作超簡單！**")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### **玩法（多空分開）**")
    direction = st.radio("方向", ["CALL 📈 (看漲)", "PUT 📉 (看跌)"], horizontal=True)
    target_cp = "CALL" if "CALL" in direction else "PUT"

with c2:
    st.markdown("### **月份**")
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]

    if not future_contracts:
        st.error("找不到可用月份")
        st.stop()

    default_index = len(future_contracts) - 3 if len(future_contracts) > 3 else 0
    sel_contract = st.selectbox("📅 選月份", future_contracts, index=default_index)

with c3:
    st.markdown("### **槓桿**")
    target_lev = st.slider("想要幾倍？", 2.0, 20.0, 5.0, 0.5)

st.info(f"🎯 **目標：{sel_contract} 月，{target_lev} 倍槓桿，只找 {target_cp}！**")

# ---------------------------------
# 計算 (含 Black-Scholes 理論價)
# ---------------------------------
def bs_price_delta(S, K, T, r, sigma, cp):
    """計算理論價格與 Delta"""
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if cp == "CALL" else max(K - S, 0)
        return intrinsic, (1.0 if intrinsic > 0 else 0.0)
        
    try:
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if cp == "CALL":
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
            delta = norm.cdf(d1)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            delta = -norm.cdf(-d1)
            
        return float(price), float(delta)
    except:
        return 0.0, 0.5

if st.button("🎯 **找最佳合約！**", type="primary", use_container_width=True):
    target_df = df_latest[
        (df_latest["contract_date"].astype(str) == str(sel_contract)) & 
        (df_latest["call_put"].str.upper() == target_cp)
    ].copy()

    if target_df.empty:
        st.error(f"{sel_contract} 無 {target_cp} 資料")
        st.stop()

    try:
        y, m = int(sel_contract[:4]), int(sel_contract[4:6])
        exp_date = date(y, m, 15)
        data_dt = latest_date.date()
        days_left = max((exp_date - data_dt).days, 1)
    except:
        days_left = 30

    T = days_left / 365.0

    results = []
    
    # 計算平均 IV 作為無成交合約的參考
    valid_ivs = pd.to_numeric(target_df['implied_volatility'], errors='coerce').dropna()
    avg_iv = valid_ivs.median() if not valid_ivs.empty else 0.25

    for _, row in target_df.iterrows():
        try:
            K = float(row["strike_price"])
            price = float(row["close"])
            volume = int(row["volume"])
            cp = str(row["call_put"]).upper()
            
            # 優先用官方 IV，沒有就用平均值
            iv_val = float(row.get("implied_volatility", 0))
            if iv_val <= 0 or np.isnan(iv_val):
                iv_val = avg_iv
                
        except:
            continue

        if volume <= 0: continue
        if price < 0.1: continue

        # 計算理論價與 Delta
        bs_price, delta = bs_price_delta(S_current, K, T, 0.02, iv_val, cp)
        delta_abs = abs(delta)
        
        if price > 0:
            leverage = (delta_abs * S_current) / price
        else:
            leverage = 0

        is_itm = (cp == "CALL" and K <= S_current) or (cp == "PUT" and K >= S_current)
        
        # 乖離率：市價 vs 理論價
        deviation = (price - bs_price) / bs_price * 100 if bs_price > 0 else 0

        results.append({
            "類型": "CALL 📈" if cp == "CALL" else "PUT 📉",
            "履約價": int(K),
            "權利金": round(price, 1),
            "理論價": round(bs_price, 1),
            "乖離%": round(deviation, 1),
            "成交量": volume,
            "槓桿": round(leverage, 2),
            "Delta": round(delta_abs, 2),
            "成本": int(price * 50),
            "價內": "✅" if is_itm else "⚠️",
            "CP": "C" if cp == "CALL" else "P",
        })

    df_res = pd.DataFrame(results)

    if df_res.empty:
        st.warning(f"⚠️ 該月份無 {target_cp} 真成交合約")
        st.stop()

    df_res["差距"] = (df_res["槓桿"] - float(target_lev)).abs()
    df_res = df_res.sort_values(["差距", "成交量"], ascending=[True, False]).reset_index(drop=True)

    best = df_res.iloc[0]

    st.balloons()
    
    bg_color = "#d4edda" if target_cp == "CALL" else "#f8d7da"
    border_color = "#28a745" if target_cp == "CALL" else "#dc3545"

    st.markdown(f"## 🎉 **最佳 {target_cp} 合約！**")
    st.markdown(
        f"""
<div style='background: linear-gradient(135deg, {bg_color}, #ffffff); padding: 25px;
            border-radius: 15px; border: 3px solid {border_color}; text-align: center;'>
<h1>🚀 **{int(best["履約價"]):,}**</h1>
<h2>⚡ **{best["槓桿"]}x** (目標 {target_lev}x)</h2>
<p><strong>權利金 {best["權利金"]} (理論 {best["理論價"]}) | 乖離 {best["乖離%"]}%</strong></p>
<p><strong>{best["類型"]} | {best["Delta"]} Δ | {int(best["成交量"]):,} 張 | ${int(best["成本"]):,}</strong></p>
<h3>📋 下單指令：</h3>
<code style='background: white; padding: 12px; border-radius: 8px; font-size: 18px;'>
TXO {sel_contract} {best["CP"]}{int(best["履約價"])} 買進 1 口
</code>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown(f"## 📋 **{target_cp} 真成交清單** (含理論價)")
    
    show_df = df_res[[
        "履約價", "權利金", "理論價", "乖離%", "成交量", "槓桿", "Delta", "成本", "價內", "差距"
    ]].head(20).copy()
    
    show_df["成交量"] = show_df["成交量"].map(lambda x: f"{int(x):,}")
    show_df["成本"] = show_df["成本"].map(lambda x: f"${int(x):,}")
    
    st.dataframe(show_df, use_container_width=True)

st.caption("⚠️ 期權有歸零風險，僅供學習 | 貝伊果屋出品")
