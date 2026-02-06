"""
🔰 台指期權雙模式系統 (終極診斷版)
- 加入強力 Debug 模式：搜尋失敗時，直接印出資料庫樣本
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

# =========================
# Session State
# =========================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權診斷版", layout="wide", page_icon="🔥")

# ---------------------------------
# 資料載入 (保留原始格式以供診斷)
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token):
    dl = DataLoader()
    dl.login_by_token(api_token=token)
    end_str = date.today().strftime("%Y-%m-%d")
    start_str = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
    
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=start_str, end_date=end_str)
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
    except: S = 23000.0

    opt_start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start, end_date=end_str)
    
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(end_str)
    
    # 這裡先不強制清洗，保留原始樣貌給 Debug 看
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
        st.error("無法連線")
        st.stop()

# ==========================================
# 介面開始
# ==========================================
st.markdown("# 🔥 **台指期權診斷版**")
tab1, tab2 = st.tabs(["🔰 **簡易新手機**", "🔥 **專業戰情室**"])

# ==========================================
# 分頁 1：簡易新手機
# ==========================================
with tab1:
    m1, m2 = st.columns(2)
    m1.metric("📈 加權指數", f"{S_current:,.0f}")
    m2.metric("📊 資料日期", latest_date.strftime("%Y-%m-%d"))

    st.divider()
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown("### 1️⃣ 方向")
        st.success("📈 **看漲 (CALL)**")
        
    with c2:
        st.markdown("### 2️⃣ 月份")
        if not df_latest.empty:
            # 原始資料直接顯示，不處理
            raw_contracts = sorted(df_latest["contract_date"].unique())
            sel_contract = st.selectbox("合約", raw_contracts, index=len(raw_contracts)-1 if raw_contracts else 0)
        else: sel_contract = ""

    with c3:
        st.markdown("### 3️⃣ 槓桿")
        target_lev = st.slider("倍數", 1.5, 20.0, 5.0)

    with c4:
        st.markdown("### 4️⃣ 篩選")
        safe_mode = st.checkbox("🔰 穩健模式", value=True)

    if st.button("🎯 **尋找最佳合約** (含診斷)", type="primary", use_container_width=True):
        if df_latest.empty:
            st.error("❌ 無法取得資料 (DataFrame is empty)")
        else:
            # === 診斷步驟 1：顯示選擇條件 ===
            st.info(f"🔍 正在搜尋：合約[{sel_contract}] / 方向[CALL]")

            # === 診斷步驟 2：嘗試寬鬆篩選 ===
            # 不分大小寫，去除空白
            mask_date = df_latest["contract_date"].astype(str).str.strip() == str(sel_contract).strip()
            mask_cp = df_latest["call_put"].astype(str).str.strip().str.upper() == "CALL"
            
            target_df = df_latest[mask_date & mask_cp].copy()
            
            # === 診斷結果 ===
            if target_df.empty:
                st.error("❌ 找不到任何合約！請看下方診斷報告：")
                
                with st.expander("🛠️ **資料庫診斷報告 (點我展開)**", expanded=True):
                    st.write("### 1. 你的選擇")
                    st.code(f"合約日期: '{sel_contract}' (類型: {type(sel_contract)})")
                    st.code(f"方向: 'CALL'")

                    st.write("### 2. 資料庫樣本 (前 5 筆)")
                    st.dataframe(df_latest[["contract_date", "call_put", "strike_price", "close"]].head())

                    st.write("### 3. 資料庫中的獨特值")
                    st.write("**合約日期 (Contract Date):**")
                    st.write(df_latest["contract_date"].unique())
                    st.write("**方向 (Call/Put):**")
                    st.write(df_latest["call_put"].unique())
                    
                    st.warning("請檢查：上方顯示的合約日期格式，是否與你的選擇完全一致？(有無空格？格式不同？)")
            else:
                st.success(f"✅ 找到 {len(target_df)} 筆資料！開始計算...")
                
                # ... (以下為正常計算邏輯) ...
                y, m = int(str(sel_contract)[:4]), int(str(sel_contract)[4:6])
                days_left = max((date(y, m, 15) - latest_date.date()).days, 1)
                T = days_left / 365.0
                
                if 'implied_volatility' in target_df.columns:
                    ivs = pd.to_numeric(target_df['implied_volatility'], errors='coerce').dropna()
                    a_iv = ivs.median() if not ivs.empty else 0.2
                else: a_iv = 0.2
                
                results = []
                for _, row in target_df.iterrows():
                    try:
                        K = float(row["strike_price"])
                        price = float(row["close"])
                        vol = int(row["volume"])
                        bs_p, delta = bs_price_delta(S_current, K, T, 0.02, a_iv, "CALL")
                        delta_abs = abs(delta)
                        
                        if safe_mode and delta_abs < 0.05: continue

                        if vol > 0 and price > 0:
                            calc_price = int(round(price, 0))
                            status = "🟢 成交價"
                        else:
                            calc_price = int(round(bs_p, 0))
                            status = "🔵 合理價"
                        
                        if calc_price <= 0: continue
                        
                        lev = (delta_abs * S_current) / calc_price
                        win = calculate_win_rate(delta_abs, days_left)
                        
                        results.append({
                            "履約價": int(K),
                            "參考價": calc_price,
                            "槓桿": round(lev, 2),
                            "成交量": volume,
                            "Delta": round(delta_abs, 2),
                            "勝率": round(win, 0),
                            "狀態": status,
                            "差距": abs(lev - target_lev)
                        })
                    except: continue
                
                if results:
                    results.sort(key=lambda x: x['差距'])
                    best = results[0]
                    
                    st.balloons()
                    
                    st.divider()
                    st.markdown("### 🚀 **最佳推薦合約**")
                    c1, c2 = st.columns([2, 1])
                    c1.metric(f"履約價 {best['履約價']}", f"{best['參考價']} 點", f"{best['狀態']}")
                    c2.success("📈 **看漲 CALL**")
                    
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("槓桿", f"{best['槓桿']}x")
                    k2.metric("勝率", f"{best['勝率']}%")
                    k3.metric("Delta", best['Delta'])
                    k4.metric("成交量", best['成交量'])
                    
                    st.markdown("### 📋 其他候選")
                    st.dataframe(pd.DataFrame(results).head(10)[["履約價","參考價","槓桿","勝率","Delta","狀態"]], use_container_width=True)
                else:
                    st.warning("⚠️ 有找到資料，但過濾後為空 (可能因為安全模式)")

# ==========================================
# 分頁 2：專業戰情室 (保留，暫不改)
# ==========================================
with tab2:
    st.info("請先在簡易版測試")
