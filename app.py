"""
🔰 台指期權終極控制台 (修復版)
- 槓桿鈕修復：按下立即顯示結果
- 自由選合約：任何月份、方向、槓桿
- 投組管理：一鍵加入、風險監控
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
if 'search_active' not in st.session_state:
    st.session_state.search_active = False # 控制是否顯示搜尋結果
if 'best_match' not in st.session_state:
    st.session_state.best_match = None
if 'candidates' not in st.session_state:
    st.session_state.candidates = []

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權終極控制台", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權終極控制台** (修復版)")

# ---------------------------------
# 📚 教學區 (可折疊)
# ---------------------------------
with st.expander("📚 **策略教學與風險警示 (Lead Call / Theta)**", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
        ### 🚀 **Lead Call 策略 (波段推薦)**
        1.  **選合約**：選 **遠月 (季月)**，剩餘 >90 天。
        2.  **選履約價**：找 **Delta 0.3~0.5** (價外一兩檔)，槓桿 3~6 倍。
        3.  **操作**：持有 2~8 週，待 Delta 成長。
        4.  **出場**：**剩餘 30~90 天** 賣出 (避開 Theta 加速區)。
        """)
    with c2:
        st.markdown("### 📉 **時間價值風險燈號**")
        risk_data = {
            "剩餘天數": [">90天", "30~90天", "<30天"],
            "燈號": ["🟢 安全", "🟡 警戒", "🔴 危險"],
            "動作": ["安心持有", "準備獲利了結", "強制平倉"]
        }
        st.dataframe(pd.DataFrame(risk_data), use_container_width=True)

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
        if not index_df.empty:
            S = float(index_df["close"].iloc[-1])
        else:
            S = 23000.0
    except: S = 23000.0

    opt_start = (date.today() - timedelta(days=5)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start, end_date=end_str)
    
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(end_str)
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest

with st.spinner("載入市場數據中..."):
    try:
        S_current, df_latest, latest_date = get_data(FINMIND_TOKEN)
    except:
        st.error("無法連線至數據源")
        st.stop()

# ---------------------------------
# 🔍 側邊欄：自由參數設定
# ---------------------------------
st.sidebar.header("🔍 參數設定")

# 1. 方向
direction = st.sidebar.radio("方向", ["Call (看漲)", "Put (看跌)"], index=0)
target_cp = "CALL" if "Call" in direction else "PUT"

# 2. 合約月份
if not df_latest.empty:
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
    # 預設選最遠月
    default_idx = len(future_contracts)-1 if future_contracts else 0
    sel_contract = st.sidebar.selectbox("合約月份 (自由選)", future_contracts, index=default_idx)
else:
    sel_contract = ""
    future_contracts = []

# 3. 槓桿
target_lev = st.sidebar.slider("目標槓桿", 2.0, 15.0, 5.0, 0.5)

# ---------------------------------
# 計算核心
# ---------------------------------
def bs_price_delta(S, K, T, r, sigma, cp):
    if T <= 0: return 0.0, 0.5
    try:
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        if cp == "CALL": return S*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d2), norm.cdf(d1)
        return K*np.exp(-r*T)*norm.cdf(-d2)-S*norm.cdf(-d1), -norm.cdf(-d1)
    except: return 0.0, 0.5

# ---------------------------------
# 主介面：左右分欄
# ---------------------------------
col_search, col_portfolio = st.columns([1.2, 0.8])

# =======================
# 左欄：搜尋結果與列表
# =======================
with col_search:
    st.markdown(f"### 1️⃣ 合約搜尋 ({sel_contract} {target_cp})")
    st.caption(f"大盤：{S_current:,.0f} | 槓桿目標：{target_lev}x")

    # 搜尋按鈕
    if st.button("🔥 計算並搜尋", type="primary", use_container_width=True):
        if df_latest.empty:
            st.error("無資料")
        else:
            target_df = df_latest[(df_latest["contract_date"].astype(str) == sel_contract) & 
                                  (df_latest["call_put"].str.upper() == target_cp)].copy()
            
            y, m = int(sel_contract[:4]), int(sel_contract[4:6])
            days_left = max((date(y, m, 15) - latest_date.date()).days, 1)
            T = days_left / 365.0
            
            # 取得波動率
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
                    
                    # 寬鬆過濾 (0.1 ~ 0.9) 確保有結果
                    if not (0.1 <= delta <= 0.9): continue

                    # 價格處理
                    if vol > 0 and price > 0:
                        final_price = int(round(price, 0))
                        status = "成交價"
                    else:
                        final_price = int(round(bs_p, 0))
                        status = "合理價"
                    
                    if final_price <= 0: continue
                    
                    lev = (delta * S_current) / final_price
                    
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
                        "差距": abs(lev - target_lev)
                    })
                except: continue
            
            if results:
                # 排序：按差距排
                sorted_results = sorted(results, key=lambda x: x['差距'])
                st.session_state.best_match = sorted_results[0]
                st.session_state.candidates = sorted_results
                st.session_state.search_active = True
            else:
                st.warning("無符合條件合約")
                st.session_state.search_active = False

    # === 顯示結果 ===
    if st.session_state.search_active and st.session_state.best_match:
        b = st.session_state.best_match
        
        st.divider()
        st.markdown("#### 🏆 最佳推薦 (最接近目標槓桿)")
        
        # 推薦卡片
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("履約價", f"{b['履約價']}", f"{b['類型']}")
        c2.metric("價格", f"{b['價格']} 點", b['狀態'])
        c3.metric("槓桿", f"{b['槓桿']} x")
        c4.metric("Delta", b['Delta'])
        
        if st.button("➕ 加入推薦到投組", type="secondary", use_container_width=True):
            exists = any(p['履約價'] == b['履約價'] and p['合約'] == b['合約'] and p['類型'] == b['類型'] for p in st.session_state.portfolio)
            if not exists:
                st.session_state.portfolio.append(b)
                st.toast("✅ 已加入！")
            else:
                st.toast("⚠️ 已在投組中")

        st.divider()
        st.markdown("#### 📋 其他候選 (自由選擇)")
        
        # 顯示完整清單
        cand_df = pd.DataFrame(st.session_state.candidates)
        # 按履約價排序方便看
        cand_df = cand_df.sort_values("履約價", ascending=(target_cp=="CALL"))
        
        st.dataframe(
            cand_df[["履約價", "價格", "槓桿", "Delta", "狀態", "成交量"]],
            use_container_width=True,
            hide_index=True
        )

# =======================
# 右欄：投組與風險
# =======================
with col_portfolio:
    st.markdown("### 2️⃣ 投組監控")
    
    if st.session_state.portfolio:
        pf_df = pd.DataFrame(st.session_state.portfolio)
        
        total_pts = pf_df["價格"].sum()
        total_money = total_pts * 50
        
        m1, m2 = st.columns(2)
        m1.metric("總權利金", f"{total_pts} 點")
        m2.metric("總成本", f"${total_money:,.0f}")
        
        st.divider()
        
        # 風險監控
        def get_risk(days):
            if days <= 30: return "🔴 危險 (Theta殺手)"
            if days <= 90: return "🟡 警戒 (觀察賣點)"
            return "🟢 安全 (Lead Call)"

        pf_df["風險"] = pf_df["剩餘天"].apply(get_risk)
        
        st.dataframe(
            pf_df[["合約", "履約價", "類型", "風險"]].style.map(
                lambda x: 'color: red; font-weight: bold' if '危險' in str(x) else 
                          ('color: orange; font-weight: bold' if '警戒' in str(x) else 'color: green'), 
                subset=['風險']
            ),
            use_container_width=True,
            hide_index=True
        )
        
        if st.button("🗑️ 清空投組", use_container_width=True):
            st.session_state.portfolio = []
            st.rerun()
            
    else:
        st.info("👈 **投組目前是空的**\n請搜尋後加入合約")
