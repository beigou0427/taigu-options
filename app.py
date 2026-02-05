"""
🔰 台指期權終極戰情室 (Lead Call + 投組管理版)
- 核心策略：Lead Call (遠月/低槓桿/長期持有)
- 投組功能：一鍵加入、總成本計算、風險監控
- 介面優化：左右分欄 (左搜尋/右管理)、風險燈號
- 數據標準：期權價格整數化、成交價/合理價
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

# =========================
# 1. Session State 初始化
# =========================
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = []
if 'last_best' not in st.session_state:
    st.session_state.last_best = None

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權終極戰情室", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權終極戰情室** (Lead Call 版)")

# ---------------------------------
# 📚 教學區 (Lead Call + Theta)
# ---------------------------------
with st.expander("📚 **Lead Call 策略與時間價值曲線 (必讀)**", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        ### 🚀 **Lead Call 核心節奏**
        1.  **買進**：季月 (剩90-180天)，槓桿 3-6x，Delta 0.3-0.5。
        2.  **持有**：2-8週，讓 Delta 成長，槓桿自然放大。
        3.  **賣出**：**剩餘 30-90 天** (避開 Theta 加速區)。
        """)
    with c2:
        st.markdown("### 📉 **Theta 衰減警戒線**")
        time_data = {
            "剩餘天數": [180, 90, 60, 30, 7],
            "時間價值": ["100% (安全)", "65% (警戒)", "45% (考慮賣)", "25% (危險)", "5% (歸零)"],
            "操作": ["✅ 買進", "🔄 持有/賣出", "💰 獲利平倉", "🛑 強制出場", "❌ 勿碰"]
        }
        st.dataframe(pd.DataFrame(time_data), use_container_width=True)

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
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
    except: S = 23000.0

    opt_start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start, end_date=end_str)
    
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(end_str)
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest

with st.spinner("載入全市場資料..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("資料載入失敗")
        st.stop()

# ---------------------------------
# 🔍 參數區 (Sidebar)
# ---------------------------------
st.sidebar.header("🔍 搜尋參數")
direction = st.sidebar.radio("方向", ["Call (看漲)", "Put (看跌)"], index=0)
target_cp = "CALL" if "Call" in direction else "PUT"

if not df_latest.empty:
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
    # 預設選最遠月 (符合 Lead Call)
    def_idx = len(future_contracts)-1 if future_contracts else 0
    sel_contract = st.sidebar.selectbox("合約月份", future_contracts, index=def_idx)
else:
    sel_contract = ""

target_lev = st.sidebar.slider("目標槓桿", 2.0, 10.0, 4.5, 0.5)
st.sidebar.caption("💡 Lead Call 建議：3x - 6x")

# ---------------------------------
# 計算函數
# ---------------------------------
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

# ---------------------------------
# 主畫面：左右分欄
# ---------------------------------
col_search, col_portfolio = st.columns([1, 1])

# === 左欄：策略搜尋 ===
with col_search:
    st.markdown("### 1️⃣ 策略搜尋 (Lead Call)")
    st.caption(f"目前大盤：{S_current:,.0f} | 資料日期：{latest_date.strftime('%Y-%m-%d')}")
    
    if st.button("🔥 尋找最佳合約", use_container_width=True, type="primary"):
        if df_latest.empty:
            st.error("無資料")
        else:
            target_df = df_latest[(df_latest["contract_date"].astype(str) == sel_contract) & 
                                  (df_latest["call_put"].str.upper() == target_cp)].copy()
            
            y, m = int(sel_contract[:4]), int(sel_contract[4:6])
            days_left = max((date(y, m, 15) - latest_date.date()).days, 1)
            T = days_left / 365.0
            
            # 計算 IV 中位數
            if 'implied_volatility' in target_df.columns:
                ivs = pd.to_numeric(target_df['implied_volatility'], errors='coerce').dropna()
                avg_iv = ivs.median() if not ivs.empty else 0.2
            else: avg_iv = 0.2

            results = []
            for _, row in target_df.iterrows():
                try:
                    K = float(row["strike_price"])
                    price = float(row["close"])
                    vol = int(row["volume"])
                    
                    bs_p, delta = bs_price_delta(S_current, K, T, 0.02, avg_iv, target_cp)
                    delta = abs(delta)
                    
                    # Lead Call 篩選 (Delta 0.25 ~ 0.75)
                    if not (0.25 <= delta <= 0.75): continue

                    # 價格整數化 & 成交判斷
                    if vol > 0 and price > 0:
                        final_price = int(round(price, 0))
                        status = "成交價"
                    else:
                        final_price = int(round(bs_p, 0))
                        status = "合理價"
                    
                    if final_price <= 0: continue
                    
                    lev = (delta * S_current) / final_price
                    win = calculate_win_rate(delta, days_left)
                    
                    results.append({
                        "合約": sel_contract,
                        "類型": target_cp,
                        "履約價": int(K),
                        "價格": final_price,
                        "槓桿": round(lev, 2),
                        "Delta": round(delta, 2),
                        "剩餘天": days_left,
                        "狀態": status,
                        "成交量": vol,
                        "勝率": round(win, 1),
                        "差距": abs(lev - target_lev)
                    })
                except: continue
                
            if results:
                best = sorted(results, key=lambda x: x['差距'])[0]
                st.session_state.last_best = best
            else:
                st.warning("無符合 Lead Call 條件合約 (Delta 0.25~0.75)")
                st.session_state.last_best = None

    # 顯示搜尋結果
    if st.session_state.last_best:
        b = st.session_state.last_best
        st.divider()
        st.success(f"🎯 **推薦：{b['合約']} {b['履約價']} {b['類型']}**")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 價格", f"{b['價格']} 點")
        c2.metric("⚡ 槓桿", f"{b['槓桿']} x")
        c3.metric("⏳ 剩餘", f"{b['剩餘天']} 天")
        
        c4, c5, c6 = st.columns(3)
        c4.metric("📊 Delta", b['Delta'])
        c5.metric("📈 勝率", f"{b['勝率']}%")
        c6.metric("ℹ️ 狀態", b['狀態'])

        # 加入投組按鈕
        if st.button("➕ 加入模擬投組", type="secondary", use_container_width=True):
            # 檢查重複
            exists = any(p['履約價'] == b['履約價'] and p['合約'] == b['合約'] and p['類型'] == b['類型'] for p in st.session_state.portfolio)
            if not exists:
                st.session_state.portfolio.append(b)
                st.toast("✅ 已加入投組！")
            else:
                st.toast("⚠️ 該合約已在投組中")

# === 右欄：投組管理 ===
with col_portfolio:
    st.markdown("### 2️⃣ 模擬投組管理")
    
    if st.session_state.portfolio:
        pf_df = pd.DataFrame(st.session_state.portfolio)
        
        # 總計計算
        total_pts = pf_df["價格"].sum()
        total_money = total_pts * 50
        avg_win = pf_df["勝率"].mean()
        
        # 儀表板
        m1, m2, m3 = st.columns(3)
        m1.metric("總權利金", f"{total_pts} 點", f"NT$ {total_money:,.0f}")
        m2.metric("平均勝率", f"{avg_win:.1f}%")
        m3.metric("持倉數", f"{len(pf_df)} 口")
        
        st.divider()
        st.markdown("#### 📜 持倉明細 & 風險監控")
        
        # 風險燈號邏輯
        def get_risk_label(days):
            if days <= 30: return "🔴 危險 (Theta加速)"
            if days <= 90: return "🟡 警戒 (觀察賣點)"
            return "🟢 安全 (持有)"

        display_df = pf_df.copy()
        display_df["風險提示"] = display_df["剩餘天"].apply(get_risk_label)
        
        # 簡化顯示欄位
        show_cols = ["合約", "履約價", "類型", "價格", "Delta", "風險提示"]
        
        # 樣式設定
        st.dataframe(
            display_df[show_cols].style.map(
                lambda x: 'color: red; font-weight: bold' if '危險' in str(x) else 
                          ('color: orange; font-weight: bold' if '警戒' in str(x) else 'color: green'), 
                subset=['風險提示']
            ),
            use_container_width=True,
            hide_index=True
        )
        
        # 智慧建議
        min_days = pf_df["剩餘天"].min()
        if min_days <= 30:
            st.error(f"🚨 **緊急警報**：有合約剩餘 {min_days} 天，進入 Theta 死亡區，請立即平倉！")
        elif min_days <= 90:
            st.warning(f"⚠️ **獲利提醒**：有合約進入 90 天倒數，時間價值開始加速流失，請準備獲利了結。")
            
        if st.button("🗑️ 清空投組", use_container_width=True):
            st.session_state.portfolio = []
            st.rerun()
            
    else:
        st.info("👈 **目前投組為空**\n\n請在左側搜尋合約，並點擊「加入模擬投組」")
        st.caption("透過投組管理，您可以一次監控多口合約的風險與總成本。")

