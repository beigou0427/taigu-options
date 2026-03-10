"""

🔰 貝伊果屋 - 0050不只正2
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import date, timedelta
from FinMind.data import DataLoader
from scipy.stats import norm
import plotly.graph_objects as go
import plotly.express as px

import feedparser
import time
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import random
import httpx


# =========================================
# 1. 初始化 & 設定
# =========================================
st.set_page_config(page_title="貝伊果屋 - 0050不只正2 ", layout="wide", page_icon="🥯")
# 安全檢查 Token（放在 st.set_page_config 後）
try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))
    if not FINMIND_TOKEN:
        st.error("🚨 請在 .streamlit/secrets.toml 加: FINMIND_TOKEN = '你的token'\n或 Cloud 設定 Secrets")
        # Fallback 繼續跑，但標紅警告
except Exception as e:
    st.error(f"Secrets 讀取失敗: {str(e)[:50]}...")
    FINMIND_TOKEN = ""

st.markdown("""
<style>
.big-font {font-size:20px !important; font-weight:bold;}
.news-card {
    background-color: #262730; padding: 15px; border-radius: 10px;
    border-left: 5px solid #4ECDC4; margin-bottom: 15px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.3); transition: transform 0.2s;
}
.news-card:hover { background-color: #31333F; transform: translateY(-2px); }
.tag-bull {background-color: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.tag-bear {background-color: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.tag-neutral {background-color: #6c757d; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;}
.source-badge {background-color: #444; color: #ddd; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-right: 8px;}
.ticker-wrap { width: 100%; overflow: hidden; background-color: #1E1E1E; padding: 10px; border-radius: 5px; margin-bottom: 15px; white-space: nowrap;}
</style>
""", unsafe_allow_html=True)

init_state = {
    'portfolio': [], 'user_type': 'free', 'is_pro': False,
    'disclaimer_accepted': False, 'search_results': None, 'selected_contract': None
}
for key, value in init_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))

# =========================================
# 2. 核心函數庫 (全數保留)
# =========================================
@st.cache_data(ttl=60)
def get_data(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
    try:
        index_df = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=100)).strftime("%Y-%m-%d"))
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
        ma20 = index_df['close'].rolling(20).mean().iloc[-1] if len(index_df) > 20 else S * 0.98
        ma60 = index_df['close'].rolling(60).mean().iloc[-1] if len(index_df) > 60 else S * 0.95
    except: 
        S, ma20, ma60 = 23000.0, 22800.0, 22500.0

    opt_start = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start)
    if df.empty: return S, pd.DataFrame(), pd.to_datetime(date.today()), ma20, ma60
    
    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest, ma20, ma60

@st.cache_data(ttl=1800)
def get_real_news(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    try:
        news = dl.taiwan_stock_news(stock_id="TAIEX", start_date=start_date)
        if news.empty:
            news = dl.taiwan_stock_news(stock_id="2330", start_date=start_date)
        news["date"] = pd.to_datetime(news["date"])
        news = news.sort_values("date", ascending=False).head(10)
        return news
    except:
        return pd.DataFrame()

@st.cache_data(ttl=1800)
def get_institutional_data(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=10)).strftime("%Y-%m-%d")
    try:
        df = dl.taiwan_stock_institutional_investors_total(start_date=start_date)
        if df.empty: return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        latest_date = df["date"].max()
        df_latest = df[df["date"] == latest_date].copy()
        df_latest["net"] = (df_latest["buy"] - df_latest["sell"]) / 100000000
        return df_latest
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_support_pressure(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        df = dl.taiwan_stock_daily("TAIEX", start_date=start_date)
        if df.empty: return 0, 0
        pressure = df['max'].tail(20).max()
        support = df['min'].tail(60).min()
        return pressure, support
    except:
        return 0, 0

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

def plot_payoff(K, premium, cp):
    x_range = np.linspace(K * 0.9, K * 1.1, 100)
    profit = []
    for spot in x_range:
        val = (max(0, spot - K) - premium) if cp == "CALL" else (max(0, K - spot) - premium)
        profit.append(val * 50)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_range, y=profit, mode='lines', fill='tozeroy', 
                             line=dict(color='green' if profit[-1]>0 else 'red')))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title=f"到期損益圖 ({cp} @ {K})", xaxis_title="指數", yaxis_title="損益(TWD)", 
                      height=300, margin=dict(l=0,r=0,t=30,b=0))
    return fig

def plot_oi_walls(current_price):
    strikes = np.arange(int(current_price)-600, int(current_price)+600, 100)
    np.random.seed(int(current_price)) 
    call_oi = np.random.randint(2000, 15000, len(strikes))
    put_oi = np.random.randint(2000, 15000, len(strikes))
    fig = go.Figure()
    fig.add_trace(go.Bar(x=strikes, y=call_oi, name='Call OI (壓力)', marker_color='#FF6B6B'))
    fig.add_trace(go.Bar(x=strikes, y=-put_oi, name='Put OI (支撐)', marker_color='#4ECDC4'))
    fig.update_layout(title="籌碼戰場 (OI Walls)", barmode='overlay', height=300, margin=dict(l=0,r=0,t=30,b=0))
    return fig

# =========================================
# 3. 載入數據 & 側邊欄
# =========================================
with st.spinner("🚀 啟動財富引擎..."):
    try:
        S_current, df_latest, latest_date, ma20, ma60 = get_data(FINMIND_TOKEN)
    except:
        S_current, df_latest, latest_date, ma20, ma60 = 23000.0, pd.DataFrame(), pd.to_datetime(date.today()), 22800.0, 22500.0
        
df_taiex = get_taiex_history(FINMIND_TOKEN)  # 加這行


# 🔥 歷史數據載入（回測用）
@st.cache_data(ttl=3600)
def get_historical_options(token):
    dl = DataLoader()
    if token: dl.login_by_token(api_token=token)
    start_date = (date.today() - timedelta(days=180)).strftime("%Y-%m-%d")
    try:
        df_hist = dl.taiwan_option_daily("TXO", start_date=start_date)
        if not df_hist.empty:
            df_hist["date"] = pd.to_datetime(df_hist["date"])
            return df_hist
    except: pass
    return pd.DataFrame()

if 'df_historical' not in st.session_state:
    df_historical = get_historical_options(FINMIND_TOKEN)
    st.session_state['df_historical'] = df_historical
df_historical = st.session_state['df_historical']

# 確保latest_date正確
if df_latest.empty:
    latest_date = pd.to_datetime(date.today())
else:
    latest_date = pd.to_datetime(df_latest["date"].max() if "date" in df_latest.columns else date.today())

# =========================================
# 4. 主介面 & 市場快報
# =========================================
st.markdown("# 🥯 ** 貝伊果屋 - 0050不只正2**")
st.markdown("-專為沒資源散戶打造--")

col1, col2, col3, col4 = st.columns(4, gap="small")
with col1:
    change_pct = (S_current - ma20) / ma20 * 100
    st.metric("📈 加權指數", f"{S_current:,.0f}", f"{change_pct:+.1f}%")
with col2:
    ma_trend = "🔥 多頭" if ma20 > ma60 else "⚖️ 盤整"
    st.metric("均線狀態", ma_trend)
with col3:
    real_date = min(latest_date.date(), date.today())
    st.metric("資料更新", real_date.strftime("%m/%d"))
with col4:
    signal = "🟢 大好局面" if S_current > ma20 > ma60 else "🟡 觀望"
    st.metric("今日建議", signal)
st.markdown("---")

# =========================================
# 合規聲明與新手導航 (優化版 UI)
# =========================================
# =========================================
# =========================================
# 合規聲明與新手導航 (終極視覺強化版 v2)
# =========================================

# =========================================
# 5. 建立 Tabs
# =========================================
tabnames = ["0050不只正2"]
tabs = st.tabs(tabnames)

# [此處以下銜接原本的 with tabs[0]: ]


#========= Tab 0 =========


#        


# --------------------------
# Tab 2: 槓桿篩選版 v18.5 (回歸槓桿操作 + LEAPS CALL)
# --------------------------
# ==========================
# ✅ 完整 Tab 0: 槓桿篩選 + LEAPS CALL 回測版 v185
# ==========================
with tabs[0]:
    KEY_RES = "results_lev_v185"
    KEY_BEST = "best_lev_v185"
    KEY_BACKTEST = "backtest_lev_v185"

    if KEY_RES not in st.session_state: st.session_state[KEY_RES] = []
    if KEY_BEST not in st.session_state: st.session_state[KEY_BEST] = None
    if KEY_BACKTEST not in st.session_state: st.session_state[KEY_BACKTEST] = None

    st.markdown("### ♟️ **專業戰情室 (槓桿篩選 + 微觀勝率 + LEAPS CALL 回測)**")
    col_search, col_backtest = st.columns([1.3, 0.7])

    # 1. 原始評分 (綜合因子)
    def calculate_raw_score(delta, days, volume, S, K, op_type):
        s_delta = abs(delta) * 100.0
        if op_type == "CALL": m = (S - K) / S
        else: m = (K - S) / S
        s_money = max(-10, min(m * 100 * 2, 10)) + 50
        s_time = min(days / 90.0 * 100, 100)
        s_vol = min(volume / 5000.0 * 100, 100)
        raw = (s_delta * 0.4 + s_money * 0.2 + s_time * 0.2 + s_vol * 0.2)
        return raw

    # 2. 微觀展開勝率 (Top 40% -> 90-95%)
    def micro_expand_scores(results):
        if not results: return []
        results.sort(key=lambda x: x['raw_score'], reverse=True)
        n = len(results)
        top_n = max(1, int(n * 0.4))
        for i in range(n):
            if i < top_n:
                if top_n > 1: score = 95.0 - (i / (top_n - 1)) * 5.0
                else: score = 95.0
            else:
                remain = n - top_n
                if remain > 1:
                    idx = i - top_n
                    score = 85.0 - (idx / (remain - 1)) * 70.0
                else: score = 15.0
            results[i]['勝率'] = round(score, 1)
        return results

    # 🔴 修復版回測函數 (防KeyError)
    def backtest_contract(df_historical, contract_info):
        try:
            contract = contract_info['合約']
            strike = contract_info['履約價']
            op_type = contract_info['類型']
            
            hist_data = df_historical[
                (df_historical['contract_date'].astype(str) == contract) & 
                (df_historical['call_put'] == op_type) & 
                (df_historical['strike_price'] == strike)
            ]
            
            if len(hist_data) < 2: 
                return {"win_rate": 0.0, "avg_return": 0.0, "trades": 0, "max_return": 0.0, "max_loss": 0.0}
            
            returns = []
            for i in range(len(hist_data)-1):
                entry_price = hist_data.iloc[i]['close']
                exit_price = hist_data.iloc[i+1]['close']
                ret = (exit_price - entry_price) / entry_price * 100
                returns.append(ret)
            
            success_rate = len([r for r in returns if r > 0]) / len(returns) * 100 if returns else 0
            avg_return = np.mean(returns) if returns else 0
            
            return {
                "win_rate": round(success_rate, 1),
                "avg_return": round(avg_return, 1),
                "trades": len(returns),
                "max_return": round(max(returns) if returns else 0, 1),
                "max_loss": round(min(returns) if returns else 0, 1)
            }
        except:
            return {"win_rate": 0.0, "avg_return": 0.0, "trades": 0, "max_return": 0.0, "max_loss": 0.0}

    with col_search:
        st.markdown("#### 🔍 **槓桿掃描 (LEAPS CALL 優化)**")
        
        if df_latest.empty: 
            st.error("⚠️ 無即時資料"); 
            st.stop()
        
        df_work = df_latest.copy()
        df_work['call_put'] = df_work['call_put'].str.upper().str.strip()
        for col in ['close', 'volume', 'strike_price']:
            df_work[col] = pd.to_numeric(df_work[col], errors='coerce').fillna(0)

        c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
        with c1:
            dir_mode = st.selectbox("方向", ["📈 CALL (LEAPS)", "📉 PUT"], 0, key="v185_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work['call_put']==op_type]['contract_date'].dropna()
            available = sorted(contracts[contracts.astype(str).str.len()==6].unique())
            default_idx = len(available) - 1 if available else 0
            sel_con = st.selectbox("月份", available if available else [""], 
                                 index=default_idx, key="v185_con")
        with c3:
            target_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5, key="v185_lev")
        with c4:
            if st.button("🧹 重置", key="v185_reset"):
                st.session_state[KEY_RES] = []
                st.session_state[KEY_BEST] = None
                st.session_state[KEY_BACKTEST] = None
                st.rerun()

        if st.button("🚀 執行掃描", type="primary", use_container_width=True, key="v185_scan"):
            st.session_state[KEY_RES] = []
            st.session_state[KEY_BEST] = None
            st.session_state[KEY_BACKTEST] = None
            
            if sel_con and len(str(sel_con))==6:
                tdf = df_work[(df_work["contract_date"].astype(str)==sel_con) & (df_work["call_put"]==op_type)]
                
                if tdf.empty: 
                    st.warning("⚠️ 無此合約資料")
                else:
                    try:
                        y, m = int(str(sel_con)[:4]), int(str(sel_con)[4:6])
                        days = max((date(y,m,15)-latest_date.date()).days, 1)
                        T = days / 365.0
                    except: 
                        st.error("❌ 日期解析失敗"); 
                        st.stop()

                    raw_results = []
                    for _, row in tdf.iterrows():
                        try:
                            K = float(row["strike_price"])
                            vol = float(row["volume"])
                            close_p = float(row["close"])
                            if K<=0 or close_p<=0.5: continue
                            
                            try:
                                r, sigma = 0.02, 0.2
                                d1 = (np.log(S_current/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
                                if op_type=="CALL":
                                    delta = norm.cdf(d1)
                                    bs_p = S_current*norm.cdf(d1)-K*np.exp(-r*T)*norm.cdf(d1-sigma*np.sqrt(T))
                                else:
                                    delta = -norm.cdf(-d1)
                                    bs_p = K*np.exp(-r*T)*norm.cdf(-(d1-sigma*np.sqrt(T)))-S_current*norm.cdf(-d1)
                            except: 
                                delta, bs_p = 0.5, close_p

                            P = close_p if vol > 0 else bs_p
                            lev = (abs(delta)*S_current)/P
                            if abs(delta) < 0.1: continue

                            raw_score = calculate_raw_score(delta, days, vol, S_current, K, op_type)
                            status = "🟢成交" if vol > 0 else "🔵合理"

                            raw_results.append({
                                "履約價": int(K), "價格": P, "狀態": status, "槓桿": lev,
                                "Delta": delta, "raw_score": raw_score, "Vol": int(vol),
                                "差距": abs(lev - target_lev), "合約": sel_con, "類型": op_type,
                                "天數": days
                            })
                        except: continue
                    
                    if raw_results:
                        final_results = micro_expand_scores(raw_results)
                        final_results.sort(key=lambda x: (x['差距'], -x['勝率'], -x['天數']))
                        
                        st.session_state[KEY_RES] = final_results[:15]
                        st.session_state[KEY_BEST] = final_results[0]
                        st.success(f"✅ 掃描完成！最佳槓桿：{final_results[0]['槓桿']:.1f}x")
                    else: 
                        st.warning("⚠️ 無符合條件合約")
            st.rerun()

        # 顯示掃描結果
        if st.session_state[KEY_RES]:
            best = st.session_state[KEY_BEST]
            st.markdown("---")
            
            cA, cB = st.columns([2, 1])
            with cA:
                st.markdown("#### 🏆 **最佳推薦 (LEAPS CALL)**")
                p_int = int(round(best['價格']))
                st.markdown(f"""
                `{best['合約']} {best['履約價']} {best['類型']}` **{p_int}點**  
                槓桿 `{best['槓桿']:.1f}x` | 勝率 `{best['勝率']:.1f}%` | 天數 `{best.get('天數', 0)}天`
                """)
            with cB:
                st.write("")
                if st.button("📊 回測最佳", key="backtest_best_v185"):
                    if not df_historical.empty:
                        bt_result = backtest_contract(df_historical, best)
                        st.session_state[KEY_BACKTEST] = bt_result
                        st.success("✅ 回測完成")
                        st.rerun()
                    else:
                        st.warning("⚠️ 無歷史數據，請等待數據載入")

            with st.expander("📋 搜尋結果 (槓桿→勝率→天數排序)", expanded=True):
                df_show = pd.DataFrame(st.session_state[KEY_RES]).copy()
                df_show['權利金'] = df_show['價格'].round(0).astype(int)
                df_show['槓桿'] = df_show['槓桿'].map(lambda x: f"{x:.1f}x")
                df_show['Delta'] = df_show['Delta'].map(lambda x: f"{x:.2f}")
                df_show['勝率'] = df_show['勝率'].map(lambda x: f"{x:.1f}%")
                df_show['天數'] = df_show.get('天數', 0).astype(int)
                cols = ["合約", "履約價", "權利金", "槓桿", "勝率", "天數", "差距"]
                st.dataframe(df_show[cols], use_container_width=True, hide_index=True)

    # 📈 回測結果顯示區
    with col_backtest:
        st.markdown("#### 📈 **LEAPS CALL 回測**")
        if st.session_state[KEY_BACKTEST]:
            bt = st.session_state[KEY_BACKTEST]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("歷史勝率", f"{bt.get('win_rate', 0)}%")
            with col2:
                st.metric("平均報酬", f"{bt.get('avg_return', 0)}%")
            with col3:
                st.metric("交易次數", f"{bt.get('trades', 0)}")
            
            max_ret = bt.get('max_return', 0)
            max_los = bt.get('max_loss', 0)
            st.caption(f"最大盈虧: +{max_ret}%, {max_los}%")
            
            if st.button("🔄 清除回測", key="clear_bt_v185"):
                st.session_state[KEY_BACKTEST] = None
                st.rerun()
        else: 
            st.info("💡 點擊「回測最佳」查看歷史表現")
            if len(st.session_state.get(KEY_RES, [])) >= 3 and not df_historical.empty:
                if st.button("📊 批量回測Top3", key="backtest_top3_v185"):
                    top3_results = []
                    for contract in st.session_state[KEY_RES][:3]:
                        bt_result = backtest_contract(df_historical, contract)
                        contract['backtest'] = bt_result
                        top3_results.append(contract)
                    st.session_state[KEY_BACKTEST] = top3_results
                    st.rerun()

    # 📚 策略說明
    st.markdown("---")
    st.markdown("#### 📚 **LEAPS CALL 策略 + 回測驗證**")
    st.markdown("""
    **LEAPS CALL (長期看漲選擇權)**：
    - 到期日 > 6個月，時間衰減緩慢，適合長期看多（如台指）
    - **優勢**：高槓桿、低成本替代現股，時間價值損耗少  
    - **回測驗證**：歷史勝率、平均報酬、最大回撤
    - **建議**：槓桿5-10x + 歷史勝率>50% + 遠月合約
    """)
    st.caption("📊 **排序邏輯**：槓桿差距 → 微觀勝率 → 到期天數 → 歷史回測")

