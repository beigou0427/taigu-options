"""
🔰 台指期權終極新手機：專業術語版 + 情緒特效
- 原版功能：預設最遠月份、成交價/合理價、10大警示
- 新增特效：🎈 氣球、❄️ 雪花、🍞 Toast
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

# =========================
# FINMIND TOKEN
# =========================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權新手器** (專業版)")

# ---------------------------------
# 📚 新手教學區 (已收折)
# ---------------------------------
with st.expander("📚 **新手村：3分鐘看懂你在選什麼（點我展開）**", expanded=False):
    st.markdown("""
    ### 🐣 **第一課：什麼是 CALL 跟 PUT？**
    *   **CALL (買權)** 📈：覺得台指會 **大漲**。
    *   **PUT (賣權)** 📉：覺得台指會 **大跌**。

    ### 💰 **第二課：成交價 vs 合理價**
    *   **🟢 成交價**：市場真實交易價（有成交量）
    *   **🔵 合理價**：Black-Scholes 理論計算價（無成交時參考）
    
    ### 📊 **第三課：關鍵數字**
    *   **價內 (ITM)**：現在履約會賺錢。槓桿低、勝率高。
    *   **Delta (Δ)**：跟漲係數。0.5 代表台指漲 1 點，合約漲 0.5 點。
    *   **遠月合約**：時間價值流失慢，適合波段持有。
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
    display_date = max(latest_date, pd.to_datetime(data_date))

    return S_current, df_latest, display_date

with st.spinner("載入全市場資料..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("資料載入失敗，請檢查 Token 或網路")
        st.stop()

m1, m2 = st.columns(2)
m1.metric("📈 加權指數", f"{S_current:,.0f}")
m2.metric("📊 資料日期", latest_date.strftime("%Y-%m-%d"))

if df_latest.empty: st.stop()

# ---------------------------------
# 操作區
# ---------------------------------
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown("### 1️⃣ 方向")
    direction = st.radio("預測", ["CALL 📈 (看漲)", "PUT 📉 (看跌)"], horizontal=True, label_visibility="collapsed")
    target_cp = "CALL" if "CALL" in direction else "PUT"

with c2:
    st.markdown("### 2️⃣ 月份 (預設遠月)")
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
    
    # 預設選最遠月合約 (波段持有)
    default_idx = len(future_contracts) - 1 if future_contracts else 0
    sel_contract = st.selectbox("合約", future_contracts, index=default_idx, label_visibility="collapsed")

with c3:
    st.markdown("### 3️⃣ 槓桿")
    target_lev = st.slider("倍數", 1.5, 20.0, 5.0, 0.5, label_visibility="collapsed")

with c4:
    st.markdown("### 4️⃣ 篩選")
    safe_mode = st.checkbox("🔰 穩健模式", value=True, help="剔除深價外高風險合約")

# ---------------------------------
# 核心計算邏輯
# ---------------------------------
def bs_price_delta(S, K, T, r, sigma, cp):
    """Black-Scholes 模型"""
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

def calculate_win_rate(delta, days, hist_win=0.80, margin_call=0.02, cost=0.015):
    """勝率估算"""
    if days <= 0: return 0.0
    p_itm = delta
    raw_win = (p_itm * 0.7 + hist_win * 0.3) 
    adj_win = raw_win * (1 - margin_call) * (1 - cost) * 100
    return min(max(adj_win, 1.0), 99.0)

if st.button("🎯 **尋找最佳合約**", type="primary", use_container_width=True):
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

    # 計算隱含波動率中位數
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
            
            iv_val = float(row.get("implied_volatility", 0))
            if iv_val <= 0 or np.isnan(iv_val): iv_val = avg_iv

            bs_price, delta = bs_price_delta(S_current, K, T, 0.02, iv_val, target_cp)
            delta_abs = abs(delta)

            if safe_mode and delta_abs < 0.15: continue

            # 修改點：成交價 vs 合理價
            if volume > 0 and price > 0:
                calc_price = int(round(price, 0))  # 整數化
                status = "🟢 成交價"
            else:
                calc_price = int(round(bs_price, 0))  # 整數化
                status = "🔵 合理價"

            if calc_price <= 0: continue
            
            leverage = (delta_abs * S_current) / calc_price
            win_rate = calculate_win_rate(delta_abs, days_left)
            is_itm = (target_cp == "CALL" and K <= S_current) or (target_cp == "PUT" and K >= S_current)

            results.append({
                "狀態": status,
                "履約價": int(K),
                "參考價": calc_price,  # 已整數
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
        st.toast("⚠️ 找不到合約", icon="❌")
        st.stop()

    df_res = df_res.sort_values("差距").reset_index(drop=True)
    best = df_res.iloc[0]

    # === 特效1：搜尋成功 ===
    st.balloons()  # 🎈 氣球雨
    st.toast("🎉 成功找到最佳合約！", icon="🚀")
    
    # ---------------------------
    # 🏆 最佳推薦合約
    # ---------------------------
    st.markdown("### 🚀 **最佳推薦合約**")
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f"# **{int(best['履約價']):,}**")
        st.caption(f"{best['狀態']} | {best['位置']} | 成交量：{int(best['成交量']):,}")
    with c2:
        if target_cp == "CALL":
            st.success("📈 **看漲 CALL**")
        else:
            st.error("📉 **看跌 PUT**")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⚡ 槓桿倍數", f"{best['槓桿']}x")
    col2.metric("🔥 勝率估算", f"{best['勝率']}%")
    col3.metric("📊 Delta", f"{best['Delta']}")
    col4.metric("💰 參考價", f"{best['參考價']}點")
    
    st.markdown("---")

    # ---------------------------
    # ⚠️ 10大嚴厲警示 (折疊版)
    # ---------------------------
    with st.expander("⚠️ **操作前必看：10 大高風險警示 (點我展開)**", expanded=False):
        
        lev = best['槓桿']
        if lev < 6:
            st.success("1️⃣ 🟢 **風險等級：相對安全** (槓桿 <6x)，但仍有虧損風險。")
        elif lev < 12:
            st.warning("1️⃣ 🟡 **風險等級：中等** (槓桿 6~12x)，波動劇烈，務必設停損。")
        else:
            st.error("1️⃣ 🔴 **風險等級：極度危險** (槓桿 >12x)，新手慎入，極易歸零。")

        profit_100 = int(best['Delta'] * 100 * 50)
        st.info(f"2️⃣ 📊 **雙面情境**：台指做對 100 點賺 **${profit_100:,}**；做錯 100 點虧 **同樣金額**。")

        contract_cost = best['參考價'] * 50
        st.error(f"3️⃣ 💰 **資金鐵律**：1 口成本 **${int(contract_cost):,}**。本金至少要準備 **20倍**，否則不要碰！")

        wr = best['勝率']
        st.markdown(f"4️⃣ 📉 **機率**：勝率約 **{wr}%**，代表有 **{100-wr:.0f}%** 機率會賠錢。")

        delta = best['Delta']
        st.markdown(f"5️⃣ 🧠 **波動**：Delta {delta}，{'波動劇烈' if delta > 0.5 else '波動較緩'}。")

        st.error("6️⃣ 🛑 **停損鐵律**：權利金跌 **20%** 立即平倉！")
        st.warning("7️⃣ ⚖️ **倉位限制**：總帳戶勿超過 **10%** 買期權。")

        if days_left <= 7:
            st.error("8️⃣ ⏰ **時間風險**：即將到期！歸零風險極高！")
            # === 特效2：時間風險警示 ===
            st.toast("🚨 警告：即將到期！", icon="⚠️")
        else:
            st.info(f"8️⃣ ⏰ **時間優勢**：距到期還有 {days_left} 天，時間價值流失較慢 (適合波段)。")

        st.markdown("9️⃣ 🧘 **心態**：期權不是賭博，**絕不凹單**。")
        st.error("🔟 🚨 **警告**：期權有 **100% 歸零風險**，切勿借錢投資！")

    # ---------------------------
    # 📋 列表顯示
    # ---------------------------
    st.markdown("### 📋 其他候選合約")
    show_df = df_res[["狀態","履約價","參考價","槓桿","勝率","Delta","位置","成交量"]].head(20).copy()
    show_df["勝率"] = show_df["勝率"].map(lambda x: f"{x}%")
    st.dataframe(show_df, use_container_width=True)
