"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學（超詳細版）
- 數字全開（volume=0 也秀）+ 理論價模擬
- CALL / PUT 分開篩選
- 全 FinMind + Black-Scholes
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
st.markdown("# 🔥 **台指期權新手器**\n**數字全開！無成交也能算！**")

# ---------------------------------
# 🔰 超詳細新手教學區
# ---------------------------------
with st.expander("📚 **新手村：3分鐘看懂你在選什麼（點我展開）**", expanded=True):
    st.markdown("""
    ### 🐣 **第一課：什麼是 CALL 跟 PUT？**
    *   **CALL (買權)** 📈：覺得台指會 **大漲**。就像買「樂透」，漲越多賺越多。
    *   **PUT (賣權)** 📉：覺得台指會 **大跌**。就像買「保險」，跌越慘賠越少(賺越多)。

    ### 💰 **第二課：為什麼會有「槓桿」？**
    *   台指期貨一點 50 元。假設現在指數 23,000 點，一口大台價值約 115 萬。
    *   如果你買一個權利金 **100點** 的選擇權 (成本 5,000 元)。
    *   當台指漲 1%，大台賺 1.15 萬。你的選擇權若漲到 150 點 (賺 2,500 元)，等於賺了 50%。
    *   **用 5,000 元參與 115 萬的漲跌，這就是槓桿！**
    
    ### 📊 **第三課：那些難懂的數字是什麼？**
    | 名詞 | 白話解釋 |
    | :--- | :--- |
    | **履約價** | 你跟莊家約定要「買」或「賣」的價格。 |
    | **價內 (ITM)** | **現在履約你會賺錢**的狀態。例如台指 23000，你擁有「用 22000 買」的權利，這張單本身就很值錢 (內含價值)。**槓桿通常較低 (2~8倍)，像買股票。** |
    | **價外 (OTM)** | **現在履約你會賠錢**的狀態。例如台指 23000，你擁有「用 24000 買」的權利，目前這張紙是廢紙，但如果未來大漲就會翻身。**槓桿通常超高 (15~50倍)，像買樂透。** |
    | **Delta (Δ)** | **台指漲 1 點，你的權利金漲幾點？** Delta 0.5 代表台指漲 100 點，你的合約漲 50 點。 |
    | **🟢 真成交** | 市場上真的有人用這個價格買賣，價格最準。 |
    | **🔵 模擬** | 市場沒人成交 (太貴或太冷門)，這是電腦算出的「合理價」，僅供參考。 |

    ---
    **💡 懶人包：**
    *   想 **穩穩賺** (像股票) 👉 選 **2~5倍** 槓桿 (通常是**深價內**，🔵模擬居多)。
    *   想 **賭一把** (像樂透) 👉 選 **10~20倍** 槓桿 (通常是**價外**，🟢真成交居多)。
    """)

# ---------------------------------
# 資料載入
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token: str):
    if not token: raise ValueError("無 TOKEN")
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    
    end_str = date.today().strftime("%Y-%m-%d")
    start_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")

    # 1. 抓大盤
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
                S_current = 23000.0
                data_date = end_str
    except:
        S_current = 23000.0
        data_date = end_str

    # 2. 抓期權
    opt_start_str = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start_str, end_date=end_str)
    
    if df.empty: return S_current, pd.DataFrame(), pd.to_datetime(data_date)
    
    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()
    df_latest = df[df["date"] == latest_date].copy()
    
    # 顯示日期取最新的
    display_date = max(latest_date, pd.to_datetime(data_date))

    return S_current, df_latest, display_date

with st.spinner("載入全市場資料..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("資料載入失敗")
        st.stop()

m1, m2 = st.columns(2)
m1.metric("📈 加權指數", f"{S_current:,.0f}")
m2.metric("📊 資料日期", latest_date.strftime("%Y-%m-%d"))

if df_latest.empty: st.stop()

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("### 1️⃣ 方向")
    direction = st.radio("覺得會漲還跌？", ["CALL 📈 (看漲)", "PUT 📉 (看跌)"], horizontal=True)
    target_cp = "CALL" if "CALL" in direction else "PUT"

with c2:
    st.markdown("### 2️⃣ 月份")
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
    sel_contract = st.selectbox("選合約月份", future_contracts, index=0)

with c3:
    st.markdown("### 3️⃣ 風險 (槓桿)")
    target_lev = st.slider("想要放大幾倍？", 1.5, 20.0, 5.0, 0.5)

st.info(f"🎯 **目標：{sel_contract} 月，{target_lev} 倍槓桿，數字全開（含模擬）！**")

# ---------------------------------
# 計算 (含模擬)
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
        else:
            return float(K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)), float(-norm.cdf(-d1))
    except:
        return 0.0, 0.5

if st.button("🎯 **全開計算！**", type="primary", use_container_width=True):
    target_df = df_latest[
        (df_latest["contract_date"].astype(str) == str(sel_contract)) & 
        (df_latest["call_put"].str.upper() == target_cp)
    ].copy()

    try:
        y, m = int(sel_contract[:4]), int(sel_contract[4:6])
        exp_date = date(y, m, 15)
        days_left = max((exp_date - latest_date.date()).days, 1)
    except: days_left = 30
    T = days_left / 365.0

    # 計算平均 IV 供模擬用
    if 'implied_volatility' in target_df.columns:
        valid_ivs = pd.to_numeric(target_df['implied_volatility'], errors='coerce').dropna()
        avg_iv = valid_ivs.median() if not valid_ivs.empty else 0.20
    else: avg_iv = 0.20

    results = []
    for _, row in target_df.iterrows():
        try:
            K = float(row["strike_price"])
            price = float(row["close"])
            volume = int(row["volume"])
            
            # IV 取值
            iv_val = float(row.get("implied_volatility", 0))
            if iv_val <= 0 or np.isnan(iv_val): iv_val = avg_iv

            # 計算理論價
            bs_price, delta = bs_price_delta(S_current, K, T, 0.02, iv_val, target_cp)
            delta_abs = abs(delta)

            # 決定計算用價格：無成交用理論價
            if volume > 0 and price > 0:
                calc_price = price
                status = "🟢 真成交"
            else:
                calc_price = bs_price
                status = "🔵 模擬"

            if calc_price <= 0.1: continue  # 太便宜不顯示
            
            leverage = (delta_abs * S_current) / calc_price
            
            # 價內判斷
            is_itm = (target_cp == "CALL" and K <= S_current) or (target_cp == "PUT" and K >= S_current)
            itm_str = "✅ 價內" if is_itm else "⚠️ 價外"

            results.append({
                "狀態": status,
                "履約價": int(K),
                "參考價": round(calc_price, 1),
                "槓桿": round(leverage, 2),
                "成交量": volume,
                "Delta": round(delta_abs, 2),
                "位置": itm_str,
                "差距": abs(leverage - target_lev)
            })
        except: continue

    df_res = pd.DataFrame(results)
    if df_res.empty:
        st.error("無資料")
        st.stop()

    df_res = df_res.sort_values("差距").reset_index(drop=True)
    best = df_res.iloc[0]

    st.balloons()
    
    # 依照多空換顏色
    bg_color = "#d4edda" if target_cp == "CALL" else "#f8d7da"
    border_color = "#28a745" if target_cp == "CALL" else "#dc3545"

    st.markdown(f"""
    <div style='background:{bg_color};padding:20px;border-radius:10px;text-align:center;border:2px solid {border_color}'>
    <h2>🚀 最佳推薦：{best['履約價']} ({best['狀態']})</h2>
    <h3>⚡ 槓桿：{best['槓桿']}x (目標 {target_lev}x)</h3>
    <p><strong>{best['位置']} | 參考價：{best['參考價']} | Delta：{best['Delta']}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 📋 完整清單 (按槓桿接近度排序)")
    st.dataframe(df_res[["狀態","履約價","參考價","槓桿","成交量","Delta","位置"]].head(20), use_container_width=True)
