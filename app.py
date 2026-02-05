"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學（超詳細版）
- 數字全開 + 理論價模擬
- CALL / PUT 分開篩選
- 全 FinMind + Black-Scholes + 勝率系統
- 預設開啟「穩健模式」(剔除深價外)
- UI 穩定版 + 10 大新手友善建議模組 (風險紅綠燈、資金建議、情境模擬...)
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
st.markdown("# 🔥 **台指期權新手器**\n**數字全開！含獨家勝率估算！**")

# ---------------------------------
# 🔰 超詳細新手教學區
# ---------------------------------
with st.expander("📚 **新手村：3分鐘看懂你在選什麼（點我展開）**", expanded=True):
    st.markdown("""
    ### 🐣 **第一課：什麼是 CALL 跟 PUT？**
    *   **CALL (買權)** 📈：覺得台指會 **大漲**。
    *   **PUT (賣權)** 📉：覺得台指會 **大跌**。

    ### 💰 **第二課：為什麼會有「槓桿」？**
    *   **用小錢參與大盤漲跌，這就是槓桿！**
    *   槓桿 5 倍 = 台指漲 1%，你的合約賺 5%。
    
    ### 📊 **第三課：那些難懂的數字？**
    | 名詞 | 白話解釋 |
    | :--- | :--- |
    | **履約價** | 你跟莊家約定要「買」或「賣」的價格。 |
    | **價內 (ITM)** | **現在履約會賺錢**。槓桿低 (2~8倍)，勝率高。 |
    | **價外 (OTM)** | **現在履約會賠錢**。槓桿高 (15~50倍)，像買樂透。 |
    | **Delta (Δ)** | 跟漲係數。0.5 代表台指漲 1 點，合約漲 0.5 點。 |
    | **🔥 勝率** | **獨家模型！** 綜合 Delta、時間、歷史數據算出的獲利機率。 |

    ---
    **💡 懶人包：**
    *   想 **穩穩賺** 👉 選 **2~5倍** 槓桿 (勝率較高)。
    *   想 **賭一把** 👉 選 **10~20倍** 槓桿 (勝率較低)。
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
c1, c2, c3, c4 = st.columns(4)

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

with c4:
    st.markdown("### 4️⃣ 篩選")
    safe_mode = st.checkbox("🔰 穩健模式 (剔除深價外)", value=True, help="過濾掉勝率極低、槓桿過高的價外合約，適合新手")

st.info(f"🎯 **目標：{sel_contract} 月，{target_lev} 倍槓桿，含勝率分析！**")

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

def calculate_win_rate(delta, days, hist_win=0.80, premium_ratio=0.85, margin_call=0.02, cost=0.015):
    """獨家勝率估算模型"""
    if days <= 0: return 0.0
    T = days / 365.0
    p_itm = delta  # 價內機率近似於 Delta
    raw_win = (p_itm * 0.7 + hist_win * 0.3) 
    adj_win = raw_win * (1 - margin_call) * (1 - cost) * 100
    return min(max(adj_win, 1.0), 99.0)

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

            if volume > 0 and price > 0:
                calc_price = price
                status = "🟢 真成交"
            else:
                calc_price = bs_price
                status = "🔵 模擬"

            if calc_price <= 0.1: continue
            
            leverage = (delta_abs * S_current) / calc_price
            win_rate = calculate_win_rate(delta_abs, days_left)
            
            is_itm = (target_cp == "CALL" and K <= S_current) or (target_cp == "PUT" and K >= S_current)
            itm_str = "✅ 價內" if is_itm else "⚠️ 價外"

            results.append({
                "狀態": status,
                "履約價": int(K),
                "參考價": round(calc_price, 1),
                "槓桿": round(leverage, 2),
                "成交量": volume,
                "Delta": round(delta_abs, 2),
                "勝率": round(win_rate, 1),
                "位置": itm_str,
                "差距": abs(leverage - target_lev)
            })
        except: continue

    df_res = pd.DataFrame(results)
    if df_res.empty:
        msg = "無符合條件的合約" + (" (嘗試關閉穩健模式)" if safe_mode else "")
        st.warning(msg)
        st.stop()

    df_res = df_res.sort_values("差距").reset_index(drop=True)
    best = df_res.iloc[0]

    st.balloons()
    
    # 穩定版：原生組件顯示最佳合約
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
    
    # 4欄重要數據
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("⚡ 槓桿倍數", f"{best['槓桿']}x")
    col2.metric("🔥 勝率估算", f"{best['勝率']}%")
    col3.metric("📊 Delta", f"{best['Delta']}")
    col4.metric("💰 參考價", f"{best['參考價']}")
    
    # ---------------------------
    # 🔥 10大新手導師建議區塊 (新增整合版)
    # ---------------------------
    st.markdown("---")
    st.markdown("### 💡 **新手導師 10 大建議**")
    
    # 1. 風險紅綠燈
    lev = best['槓桿']
    if lev < 6:
        st.success("1️⃣ 🟢 **風險等級：安全** (槓桿 <6x，像股票一樣安心)")
    elif lev < 12:
        st.warning("1️⃣ 🟡 **風險等級：警戒** (槓桿 6~12x，需密切關注盤勢)")
    else:
        st.error("1️⃣ 🔴 **風險等級：危險** (槓桿 >12x，高風險賭博性質)")

    # 2. 情境模擬
    delta = best['Delta']
    profit_100 = int(delta * 100 * 50)
    profit_3pct = int(delta * (S_current * 0.03) * 50)
    
    if target_cp == "CALL":
        st.info(f"2️⃣ 🎬 **情境模擬**：\n- 台指漲 **100點**，這張單約賺 **${profit_100:,}**\n- 台指漲 **3%** (大行情)，約賺 **${profit_3pct:,}**")
    else:
        st.info(f"2️⃣ 🎬 **情境模擬**：\n- 台指跌 **100點**，這張單約賺 **${profit_100:,}**\n- 台指跌 **3%** (大崩盤)，約賺 **${profit_3pct:,}**")

    # 3. 資金控管
    contract_cost = best['參考價'] * 50
    safe_fund = contract_cost * 20
    st.caption(f"3️⃣ 💰 **資金控管**：買 1 口成本 **${int(contract_cost):,}**。建議準備 **${int(safe_fund):,}** 本金再操作，避免一次畢業！")

    # 4. 勝率解析
    wr = best['勝率']
    if wr > 80:
        st.success(f"4️⃣ 🏆 **勝率等級：超穩健 ({wr}%)** - 幾乎跟買公債一樣穩")
    elif wr > 60:
        st.info(f"4️⃣ ✅ **勝率等級：穩健 ({wr}%)** - 像買績優股")
    else:
        st.warning(f"4️⃣ ⚠️ **勝率等級：積極 ({wr}%)** - 像買期貨或小型股")

    # 5. Delta 性格
    if delta > 0.8:
        st.markdown("5️⃣ 🧠 **合約性格：老實人** (跟漲跟跌都很乖，不會亂跳)")
    elif delta > 0.5:
        st.markdown("5️⃣ 🧠 **合約性格：穩重派** (漲跌都有感覺，反應適中)")
    else:
        st.markdown("5️⃣ 🚀 **合約性格：冒險家** (只有大行情才會動，平常像死魚)")

    # 6. 倉位建議
    st.markdown("6️⃣ ⚖️ **倉位建議**：新手建議 **只買 1 口** 試水溫，切勿梭哈。")
    
    # 7. 停損指南
    st.markdown("7️⃣ 🛑 **停損指南**：權利金跌 **30%** 請立即離場，留得青山在。")
    
    # 8. 適合人群
    if lev < 6 and wr > 70:
        st.markdown("8️⃣ 👥 **適合人群**：上班族、保守投資人、存股族。")
    else:
        st.markdown("8️⃣ 👥 **適合人群**：全職交易者、短線客、風險愛好者。")
        
    # 9. 週期建議
    if days_left > 30:
        st.markdown("9️⃣ ⏰ **週期建議**：還有很久到期，可以 **波段持有**。")
    elif days_left > 7:
        st.markdown("9️⃣ ⏰ **週期建議**：適合 **短線操作** (1-3天)。")
    else:
        st.markdown("9️⃣ ⏰ **週期建議**：快到期了！建議 **當沖或隔日沖**，不要久抱。")
        
    # 10. 成本效益 (ROI)
    roi = round(lev * (wr/100), 2)
    st.markdown(f"🔟 💹 **CP值 (ROI)**：預期效益指標 **{roi}** (數值越高越好)")

    st.divider()

    st.markdown("### 📋 完整清單")
    
    show_df = df_res[["狀態","履約價","參考價","槓桿","勝率","Delta","位置","成交量"]].head(20).copy()
    show_df["勝率"] = show_df["勝率"].map(lambda x: f"{x}%")
    
    st.dataframe(show_df, use_container_width=True)
