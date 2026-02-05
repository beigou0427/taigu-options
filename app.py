"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學 + 槓桿真篩選 + 月份自由選
- 只顯示真成交（volume > 0）
- 無分布圖（移除 Plotly）
- TOKEN 硬編碼版（本地/Cloud 通用）
"""

import streamlit as st
import pandas as pd
import yfinance as yf
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
# 資料載入
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token: str):
    if not token:
        raise ValueError("FINMIND_TOKEN 尚未設定")

    # 1. 台指報價
    try:
        tx_data = yf.download("^TWII", period="5d", progress=False)
        if tx_data.empty:
            S_current = 23000.0  # fallback
        else:
            S_current = float(tx_data["Close"].dropna().iloc[-1])
    except:
        S_current = 23000.0

    # 2. 期權資料
    dl = DataLoader()
    dl.login_by_token(api_token=token)

    end_date = date.today().strftime("%Y-%m-%d")
    start_date = (date.today() - timedelta(days=60)).strftime("%Y-%m-%d")

    df = dl.taiwan_option_daily("TXO", start_date=start_date, end_date=end_date)
    if df.empty:
        return S_current, pd.DataFrame(), pd.Timestamp.now()
        
    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date].copy()

    return S_current, df_latest, latest_date


with st.spinner("載入報價..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except Exception as e:
        st.error(f"資料載入失敗：{e}")
        st.stop()

m1, m2 = st.columns(2)
m1.metric("📈 台指", f"{S_current:,.0f}")
m2.metric("📊 時間", latest_date.strftime("%Y-%m-%d"))

if df_latest.empty:
    st.error("目前無資料（可能是剛開盤或 TOKEN 問題）")
    st.stop()

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
st.markdown("## **🎮 操作超簡單！**")

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### **玩法**")
    mode_now = st.session_state.get("mode", "long")

    if st.button("🛡️ **長期**", type="primary" if mode_now == "long" else "secondary"):
        st.session_state.mode = "long"
    if st.button("⚡ **短期**", type="primary" if mode_now == "short" else "secondary"):
        st.session_state.mode = "short"

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
    mode_now = st.session_state.get("mode", "long")
    if mode_now == "long":
        target_lev = st.slider("穩穩賺", 1.5, 6.0, 2.5, 0.5)
    else:
        target_lev = st.slider("拚大錢", 5.0, 25.0, 12.0, 1.0)

st.info(f"🎯 **目標：{sel_contract} 月，{target_lev} 倍槓桿，只秀真成交！**")

# ---------------------------------
# 計算
# ---------------------------------
def bs_delta(S, K, T, r, sigma, cp):
    if T <= 0 or sigma <= 0:
        return 0.5
    try:
        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        if cp == "CALL":
            return float(norm.cdf(d1))
        return float(-norm.cdf(-d1))
    except:
        return 0.5

if st.button("🎯 **找最佳合約！**", type="primary", use_container_width=True):
    target_df = df_latest[df_latest["contract_date"].astype(str) == str(sel_contract)].copy()

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

    results = []
    for _, row in target_df.iterrows():
        try:
            K = float(row["strike_price"])
            price = float(row["close"])
            volume = int(row["volume"])
            cp = str(row["call_put"]).upper()
        except:
            continue

        # 只顯示真成交
        if volume <= 0:
            continue
        if price < 1:
            continue

        delta = bs_delta(S_current, K, T, 0.02, 0.25, cp)
        delta_abs = abs(delta)
        leverage = (delta_abs * S_current) / price
        is_itm = (cp == "CALL" and K <= S_current) or (cp == "PUT" and K >= S_current)

        results.append({
            "類型": "CALL 📈" if cp == "CALL" else "PUT 📉",
            "履約價": int(K),
            "權利金": round(price, 1),
            "成交量": volume,
            "槓桿": round(leverage, 2),
            "Delta": round(delta_abs, 2),
            "成本": int(price * 50),
            "價內": "✅" if is_itm else "⚠️",
            "CP": "C" if cp == "CALL" else "P",
        })

    df_res = pd.DataFrame(results)

    if df_res.empty:
        st.warning("⚠️ 該月份無真成交合約，請試其他月份")
        st.stop()

    # 排序：先找最接近目標槓桿的
    df_res["差距"] = (df_res["槓桿"] - float(target_lev)).abs()
    df_res = df_res.sort_values(["差距", "成交量"], ascending=[True, False]).reset_index(drop=True)

    best = df_res.iloc[0]

    st.balloons()
    st.markdown("## 🎉 **最佳真成交合約！**")
    st.markdown(
        f"""
<div style='background: linear-gradient(135deg, #d4edda, #c3e6cb); padding: 25px;
            border-radius: 15px; border: 3px solid #28a745; text-align: center;'>
<h1>🚀 **{int(best["履約價"]):,}**</h1>
<h2>⚡ **{best["槓桿"]}x** (目標 {target_lev}x)</h2>
<p><strong>{best["類型"]} | {best["Delta"]} Δ | {int(best["成交量"]):,} 張 | ${int(best["成本"]):,}</strong></p>
<h3>📋 下單指令：</h3>
<code style='background: white; padding: 12px; border-radius: 8px; font-size: 18px;'>
TXO {sel_contract} {best["CP"]}{int(best["履約價"])} 買進 1 口
</code>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("## 📋 **真成交清單**（按槓桿排序）")
    
    # 表格顯示格式化
    show_df = df_res[["類型", "履約價", "權利金", "成交量", "槓桿", "Delta", "成本", "價內", "差距"]].head(20).copy()
    show_df["成交量"] = show_df["成交量"].map(lambda x: f"{int(x):,}")
    show_df["成本"] = show_df["成本"].map(lambda x: f"${int(x):,}")
    
    st.dataframe(show_df, use_container_width=True)

st.caption("⚠️ 期權有歸零風險，僅供學習 | 貝伊果屋出品")
