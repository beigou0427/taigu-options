"""
🔰 台指期權終極控制台 (全自由度 + 投組管理)
- 自由度：可自選「任何月份」、「看漲看跌」、「目標槓桿」。
- 策略核心：Lead Call (預設遠月，但可手動改近月)。
- 投組管理：一鍵加入、風險燈號 (Theta監控)、總成本計算。
- 顯示優化：整數報價、成交價/合理價、候選列表。
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
if 'current_best' not in st.session_state:
    st.session_state.current_best = None

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權終極控制台", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權終極控制台** (全功能版)")

# ---------------------------------
# 📚 教學與策略區 (可折疊)
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
        st.caption("剩餘天數與操作建議")
        risk_data = {
            "剩餘天數": [">90天", "30~90天", "<30天", "<7天"],
            "燈號": ["🟢 安全", "🟡 警戒", "🔴 危險", "❌ 歸零區"],
            "狀態": ["Theta 流失慢", "Theta 開始加速", "Theta 暴增", "價值極速歸零"],
            "動作": ["安心持有", "準備獲利了結", "強制平倉", "勿碰"]
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
    
    # 抓大盤 (若失敗用期貨，再失敗用預設值)
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=start_str, end_date=end_str)
        if not index_df.empty:
            S = float(index_df["close"].iloc[-1])
        else:
            futures = dl.taiwan_futures_daily("TX", start_date=start_str, end_date=end_str)
            S = float(futures["close"].iloc[-1]) if not futures.empty else 23000.0
    except: S = 23000.0

    # 抓期權
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
        st.error("無法連線至數據源，請檢查網路或 Token")
        st.stop()

# ---------------------------------
# 🔍 側邊欄：自由參數設定
# ---------------------------------
st.sidebar.header("🔍 參數設定")

# 1. 方向
direction = st.sidebar.radio("方向", ["Call (看漲)", "Put (看跌)"], index=0)
target_cp = "CALL" if "Call" in direction else "PUT"

# 2. 合約月份 (全自由選擇)
if not df_latest.empty:
    all_contracts = sorted(df_latest["contract_date"].astype(str).unique())
    ym_now = int(latest_date.strftime("%Y%m"))
    future_contracts = [c for c in all_contracts if c.isdigit() and int(c) >= ym_now]
    
    # 預設邏輯：預設選「最遠月」(符合 Lead Call)，但使用者可以隨便改
    default_idx = len(future_contracts)-1 if future_contracts else 0
    sel_contract = st.sidebar.selectbox("合約月份 (自由選)", future_contracts, index=default_idx)
else:
    sel_contract = ""
    future_contracts = []

# 3. 槓桿與篩選
target_lev = st.sidebar.slider("目標槓桿", 2.0, 15.0, 5.0, 0.5)
safe_mode = st.sidebar.checkbox("🔰 穩健過濾 (隱藏極端值)", value=True, help="隱藏 Delta < 0.1 或 > 0.9 的極端合約")

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

def calculate_win_rate(delta, days):
    # 簡單勝率模型：Delta越高勝率越高，時間越長勝率越趨中
    return min(max((abs(delta)*0.7 + 0.8*0.3)*100, 1), 99)

# ---------------------------------
# 主介面：左右分欄
# ---------------------------------
col_search, col_portfolio = st.columns([1.2, 0.8])

# =======================
# 左欄：搜尋結果與列表
# =======================
with col_search:
    st.markdown(f"### 1️⃣ 合約搜尋 ({sel_contract} {target_cp})")
    st.caption(f"大盤指數：{S_current:,.0f} | 槓桿目標：{target_lev}x")

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
                    
                    # 穩健過濾模式
                    if safe_mode and not (0.15 <= delta <= 0.85): continue

                    # 價格處理：優先用成交價，無量用合理價
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
                        "差距": abs(lev - target_lev) # 用來找最接近目標槓桿的
                    })
                except: continue
            
            if results:
                # 排序：最接近目標槓桿的排第一
                sorted_results = sorted(results, key=lambda x: x['差距'])
                st.session_state.current_best = sorted_results[0]
                st.session_state.candidate_list = sorted_results # 儲存完整列表
            else:
                st.warning("無符合條件合約")
                st.session_state.current_best = None
                st.session_state.candidate_list = []

    # === 顯示最佳推薦 ===
    if st.session_state.current_best:
        b = st.session_state.current_best
        st.divider()
        st.markdown("#### 🏆 最佳推薦 (最接近目標槓桿)")
        
        # 推薦卡片
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("履約價", f"{b['履約價']}", f"{b['類型']}")
        c2.metric("價格", f"{b['價格']} 點", b['狀態'])
        c3.metric("槓桿", f"{b['槓桿']} x")
        c4.metric("Delta", b['Delta'])
        
        # 加入投組按鈕
        if st.button("➕ 加入此合約到投組", key="add_best", type="secondary", use_container_width=True):
            exists = any(p['履約價'] == b['履約價'] and p['合約'] == b['合約'] and p['類型'] == b['類型'] for p in st.session_state.portfolio)
            if not exists:
                st.session_state.portfolio.append(b)
                st.toast("✅ 已加入！")
            else:
                st.toast("⚠️ 已在投組中")

        # === 顯示其他候選列表 (讓使用者自己挑) ===
        st.divider()
        st.markdown("#### 📋 其他候選合約 (依履約價排序)")
        
        # 整理 DataFrame
        df_cand = pd.DataFrame(st.session_state.candidate_list)
        df_cand = df_cand.sort_values("履約價", ascending=(target_cp == "CALL")) # Call 越低越價內，Put 越高越價內
        
        # 顯示表格
        st.dataframe(
            df_cand[["履約價", "價格", "槓桿", "Delta", "狀態", "成交量"]],
            use_container_width=True,
            hide_index=True
        )

# =======================
# 右欄：投組與風險
# =======================
with col_portfolio:
    st.markdown("### 2️⃣ 模擬投組與監控")
    
    if st.session_state.portfolio:
        pf_df = pd.DataFrame(st.session_state.portfolio)
        
        # 總計
        total_pts = pf_df["價格"].sum()
        total_money = total_pts * 50
        
        m1, m2 = st.columns(2)
        m1.metric("總權利金", f"{total_pts} 點")
        m2.metric("總成本 (NT$)", f"${total_money:,.0f}")
        
        st.divider()
        
        # 風險監控邏輯
        def get_risk_label(days):
            if days <= 30: return "🔴 危險 (Theta殺手)"
            if days <= 90: return "🟡 警戒 (觀察賣點)"
            return "🟢 安全 (Lead Call)"

        pf_df["風險監控"] = pf_df["剩餘天"].apply(get_risk_label)
        
        # 顯示投組表格
        st.dataframe(
            pf_df[["合約", "履約價", "類型", "價格", "風險監控"]].style.map(
                lambda x: 'color: red; font-weight: 800' if '危險' in str(x) else 
                          ('color: orange; font-weight: 800' if '警戒' in str(x) else 'color: green'), 
                subset=['風險監控']
            ),
            use_container_width=True,
            hide_index=True
        )
        
        # 智慧警示
        min_days = pf_df["剩餘天"].min()
        if min_days <= 30:
            st.error(f"🚨 **緊急**：有合約剩 {min_days} 天，進入 Theta 加速區，建議平倉！")
        elif min_days <= 90:
            st.warning(f"⚠️ **提醒**：有合約進入 90 天倒數，請留意獲利了結。")
            
        if st.button("🗑️ 清空投組", use_container_width=True):
            st.session_state.portfolio = []
            st.rerun()
            
    else:
        st.info("👋 **投組目前是空的**")
        st.markdown("""
        **如何使用：**
        1. 在左側選好合約與條件。
        2. 點擊「計算並搜尋」。
        3. 點擊推薦卡片下方的「➕ 加入此合約」。
        """)
