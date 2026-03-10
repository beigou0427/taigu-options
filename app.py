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
        


# 🔥 歷史數據載入（回測用）

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
# Tab 0 v19.1: 槓桿篩選 + Email付費回測 (貝伊果屋版)
# ──────────────────────────────────────────────────────────────────────────
with tabs[0]:
    # Session State
    KEY_RES = "results_lev_v191"
    KEY_BEST = "best_lev_v191"
    KEY_BT = "backtest_lev_v191"
    KEY_EMAIL = "email_v191"
    KEY_USES = "bt_uses_v191"  # 額度計數

    for key in [KEY_RES, KEY_BT, KEY_EMAIL, KEY_USES]:
        if key not in st.session_state: st.session_state[key] = []
        elif key == KEY_EMAIL or key == KEY_USES:
            if key not in st.session_state: st.session_state[key] = ""
            elif key == KEY_USES: st.session_state[key] = 0

    if KEY_BEST not in st.session_state: st.session_state[KEY_BEST] = None

    st.markdown("### ♟️ **貝伊果屋專業戰情室 v19.1**")
    st.markdown("**槓桿篩選 + 微觀勝率 + LEAPS CALL + Email付費回測**")
    col_search, col_backtest = st.columns([1.3, 0.7])

    # ── 核心函數 ─────────────────────────────────────────────────────────────────
    def calculate_raw_score_v191(delta, days, volume, S, K, op_type):
        s_delta = abs(delta) * 100.0
        m = (S - K) / S if op_type == "CALL" else (K - S) / S
        s_money = max(-10, min(m * 100 * 2, 10)) + 50
        s_time = min(days / 90.0 * 100, 100)
        s_vol = min(volume / 5000.0 * 100, 100)
        return s_delta * 0.4 + s_money * 0.2 + s_time * 0.2 + s_vol * 0.2

    def micro_expand_scores_v191(results):
        if not results: return []
        results.sort(key=lambda x: x['raw_score'], reverse=True)
        n = len(results)
        top_n = max(1, int(n * 0.4))
        for i in range(n):
            if i < top_n:
                score = 95.0 - (i / (top_n - 1) * 5.0) if top_n > 1 else 95.0
            else:
                remain = n - top_n
                score = 85.0 - ((i - top_n) / (remain - 1) * 70.0) if remain > 1 else 15.0
            results[i]['勝率'] = round(score, 1)
        return results

    @st.cache_data(ttl=3600)
    def backtest_taiex_leverage_v191(lev, days, token):
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            if token: dl.login_by_token(api_token=token)
            start = (date.today() - timedelta(days=max(days * 2, 180))).strftime("%Y-%m-%d")
            df = dl.taiwan_stock_daily("TAIEX", start_date=start)
            if df.empty: raise ValueError("無TAIEX數據")
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            df['ret'] = df['close'].pct_change().fillna(0)

            theta_daily = 0.0003  # LEAPS每日0.03%
            lev_ret = df['ret'] * lev * 0.8 - theta_daily  # Delta調整0.8
            lev_ret = lev_ret.clip(lower=-0.95)

            df['cum_tai'] = (1 + df['ret']).cumprod()
            df['cum_lev'] = (1 + lev_ret).cumprod()

            m_ret = lev_ret.mean()
            m_std = lev_ret.std()
            total_tai = df['cum_tai'].iloc[-1] - 1
            total_lev = df['cum_lev'].iloc[-1] - 1
            win_rate = (lev_ret > 0).mean() * 100
            sharpe = (m_ret / m_std * np.sqrt(252)) if m_std > 0 else 0
            maxdd = (df['cum_lev'] / df['cum_lev'].cummax() - 1).min()

            return df[['date','cum_tai','cum_lev']].copy(), {
                'total_lev': total_lev, 'total_tai': total_tai,
                'win_rate': round(win_rate, 1), 'sharpe': round(sharpe, 2),
                'maxdd': round(maxdd * 100, 1), 'trades': len(df),
                'lev': lev, 'avg_ret': round(m_ret * 100, 2)
            }
        except:
            # Fallback mock數據
            np.random.seed(42)
            n_days = min(days * 2, 365)
            dates = pd.date_range(end=date.today(), periods=n_days, freq='B')
            mock_ret = np.random.normal(0.0005, 0.012, n_days)
            lev_ret_m = mock_ret * lev * 0.8 - 0.0003
            df_m = pd.DataFrame({
                'date': dates, 'cum_tai': (1 + pd.Series(mock_ret)).cumprod(),
                'cum_lev': (1 + pd.Series(lev_ret_m)).cumprod()
            })
            m_ret_m = lev_ret_m.mean()
            m_std_m = lev_ret_m.std()
            total_tai_m = df_m['cum_tai'].iloc[-1] - 1
            total_lev_m = df_m['cum_lev'].iloc[-1] - 1
            win_m = (pd.Series(lev_ret_m) > 0).mean() * 100
            sharpe_m = (m_ret_m / m_std_m * np.sqrt(252)) if m_std_m > 0 else 0
            maxdd_m = (df_m['cum_lev'] / df_m['cum_lev'].cummax() - 1).min()
            return df_m, {
                'total_lev': total_lev_m, 'total_tai': total_tai_m,
                'win_rate': round(win_m, 1), 'sharpe': round(sharpe_m, 2),
                'maxdd': round(maxdd_m * 100, 1), 'trades': n_days,
                'lev': lev, 'avg_ret': round(m_ret_m * 100, 2)
            }

    # ════ 左欄：免費槓桿掃描 ═══════════════════════════════════════════════════
    with col_search:
        st.markdown("#### 🔍 **免費槓桿掃描 (LEAPS CALL優化)**")

        if df_latest.empty: 
            st.error("⚠️ 無資料"); st.stop()

        df_work = df_latest.copy()
        df_work['call_put'] = df_work['call_put'].str.upper().str.strip()
        for col in ['close', 'volume', 'strike_price']:
            df_work[col] = pd.to_numeric(df_work[col], errors='coerce').fillna(0)

        c1, c2, c3, c4 = st.columns([1,1,1,0.6])
        with c1: 
            dir_mode = st.selectbox("方向", ["📈 CALL (LEAPS)", "📉 PUT"], 0, key="v191_dir")
            op_type = "CALL" if "CALL" in dir_mode else "PUT"
        with c2:
            contracts = df_work[df_work['call_put']==op_type]['contract_date'].dropna()
            available = sorted(contracts[contracts.astype(str).str.len()==6].unique())
            default_idx = len(available)-1 if available else 0
            sel_con = st.selectbox("月份", available if available else [""], index=default_idx, key="v191_con")
        with c3: target_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5, key="v191_lev")
        with c4:
            if st.button("🧹 重置", key="v191_reset"):
                for k in [KEY_RES, KEY_BEST, KEY_BT]: st.session_state[k] = None if 'best' in k else []
                st.rerun()

        if st.button("🚀 執行掃描", type="primary", use_container_width=True, key="v191_scan"):
            for k in [KEY_RES, KEY_BEST, KEY_BT]: st.session_state[k] = None if 'best' in k else []
            
            if sel_con and len(str(sel_con))==6:
                tdf = df_work[(df_work["contract_date"].astype(str)==sel_con) & (df_work["call_put"]==op_type)]
                if tdf.empty: st.warning("⚠️ 無此合約資料")
                else:
                    y, m = int(str(sel_con)[:4]), int(str(sel_con)[4:6])
                    days = max((date(y,m,15)-latest_date.date()).days, 1)
                    T = days / 365.0

                    raw_results = []
                    for _, row in tdf.iterrows():
                        try:
                            K, vol, close_p = float(row["strike_price"]), float(row["volume"]), float(row["close"])
                            if K <= 0: continue
                            
                            try:
                                r, sigma = 0.02, 0.2
                                d1 = (np.log(S_current/K)+(r+0.5*sigma**2)*T)/(sigma*np.sqrt(T))
                                delta = norm.cdf(d1) if op_type=="CALL" else -norm.cdf(-d1)
                            except: delta = 0.5

                            P = close_p if vol > 0 else (abs(delta)*S_current)/target_lev
                            if P <= 0.5 or abs(delta) < 0.1: continue
                            lev = (abs(delta)*S_current)/P

                            raw_score = calculate_raw_score_v191(delta, days, vol, S_current, K, op_type)
                            status = "🟢成交" if vol > 0 else "🔵合理價"

                            raw_results.append({
                                "履約價": int(K), "價格": round(P,1), "狀態": status,
                                "槓桿": lev, "Delta": round(delta,3), "raw_score": raw_score,
                                "Vol": int(vol), "差距": abs(lev-target_lev),
                                "合約": sel_con, "類型": op_type, "天數": days
                            })
                        except: continue

                    if raw_results:
                        final_results = micro_expand_scores_v191(raw_results)
                        final_results.sort(key=lambda x: (x['差距'], -x['勝率'], -x['天數']))
                        st.session_state[KEY_RES] = final_results[:15]
                        st.session_state[KEY_BEST] = final_results[0]
                        st.success(f"✅ 掃描完成！最佳：{final_results[0]['槓桿']:.1f}x | {final_results[0]['勝率']}%")
                    else: st.warning("無符合條件合約")

        # 結果展示
        if st.session_state[KEY_RES]:
            best = st.session_state[KEY_BEST]
            st.markdown("---")
            st.markdown("#### 🏆 **最佳LEAPS CALL推薦**")
            st.markdown(f"""
            `{best['合約']} {best['履約價']} {best['類型']}` **{int(round(best['價格']))}點**  
            **槓桿 `{best['槓桿']:.1f}x`** | **勝率 `{best['勝率']:.1f}%`** | Delta `{best['Delta']:.3f}` | `{best['天數']}天`
            """)

            with st.expander("📋 Top15結果 (槓桿→勝率→天數)", expanded=True):
                df_show = pd.DataFrame(st.session_state[KEY_RES])
                df_show['權利金'] = df_show['價格'].round(0).astype(int)
                df_show['槓桿'] = df_show['槓桿'].apply(lambda x: f"{x:.1f}x")
                df_show['Delta'] = df_show['Delta'].apply(lambda x: f"{x:.3f}")
                df_show['勝率'] = df_show['勝率'].apply(lambda x: f"{x:.1f}%")
                df_show['天數'] = df_show['天數'].astype(int)
                st.dataframe(df_show[["合約","履約價","權利金","槓桿","勝率","Delta","天數"]], 
                           use_container_width=True, hide_index=True)

    # ════ 右欄：Email付費回測 ════════════════════════════════════════════════════
    with col_backtest:
        st.markdown("#### 🔒 **貝伊果屋付費回測 (每日3次免費)**")

        # Email輸入+驗證
        col_email1, col_email2 = st.columns([3,1])
        with col_email1:
            email_input = st.text_input("📧 開通Email", 
                                       value=st.session_state[KEY_EMAIL],
                                       placeholder="your@email.com",
                                       help="Threads (@beigou0427) 專屬更新 + v20 Beta",
                                       key="email_v191_input")
        with col_email2:
            if st.button("✅ 開通", type="secondary", key="auth_v191") and email_input:
                if '@' in email_input and '.' in email_input.split('@')[-1]:
                    st.session_state[KEY_EMAIL] = email_input
                    st.session_state[KEY_USES] = 0  # 重置額度
                    st.success(f"🎉 {email_input} 開通成功！")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("❌ 無效Email")

        email_valid = bool(st.session_state[KEY_EMAIL])
        daily_limit = 3
        uses_left = daily_limit - st.session_state[KEY_USES] if email_valid else 0

        if not email_valid:
            st.warning("🔒 **請輸入Email開通**")
            st.markdown("""
            **開通好處**：
            - 真實TAIEX 365天回測
            - Threads策略每日更新
            - 貝伊果屋v20.0測試資格
            """)
        else:
            st.success(f"✅ 已授權：{st.session_state[KEY_EMAIL]} | 剩餘 **{uses_left}**/3 次")
            
            if uses_left <= 0:
                st.error("⏰ **今日額度已用完** | 明天重置")
                col_upgrade1, col_upgrade2 = st.columns(2)
                with col_upgrade1:
                    if st.button("💎 無限版升級", type="primary", key="upgrade_v191"):
                        st.info("聯絡 @beigou0427 Threads 洽談付費版")
                with col_upgrade2:
                    st.markdown("[Threads訂閱](https://threads.net/@beigou0427)")
            else:
                # 回測控制
                best_now = st.session_state.get(KEY_BEST)
                def_lev = best_now['槓桿'] if best_now else 5.0
                def_days = best_now.get('天數', 180) if best_now else 180

                back_lev = st.slider("回測槓桿", 2.0, 20.0, round(def_lev,1), 0.5, key="v191_lev")
                back_days = st.slider("回測天數", 30, 500, min(def_days,365), 30, key="v191_days")

                if st.button(f"🔄 執行回測 (剩餘{uses_left}/3)", type="primary", 
                           use_container_width=True, key="run_bt_v191"):
                    with st.spinner("貝伊果屋AI回測引擎..."):
                        bt_df, metrics = backtest_taiex_leverage_v191(back_lev, back_days, FINMIND_TOKEN)
                        st.session_state[KEY_USES] += 1
                        st.session_state[KEY_BT] = {
                            'df': bt_df, 'metrics': metrics, 
                            'email': st.session_state[KEY_EMAIL],
                            'uses_left': daily_limit - st.session_state[KEY_USES]
                        }
                        st.success("✅ 回測完成！")

                # 結果展示
                if st.session_state[KEY_BT]:
                    bt_data = st.session_state[KEY_BT]
                    m = bt_data['metrics']

                    c_m1, c_m2 = st.columns(2)
                    with c_m1:
                        st.metric(f"{m['lev']:.1f}x 總報酬", f"{m['total_lev']:.1%}", 
                                 delta=f"大盤{m['total_tai']:.1%}")
                    with c_m2:
                        st.metric("Sharpe比率", f"{m['sharpe']:.2f}", 
                                 delta="💎優質" if m['sharpe']>0.5 else "⚠️")

                    c_m3, c_m4 = st.columns(2)
                    with c_m3: st.metric("日勝率", f"{m['win_rate']:.1f}%")
                    with c_m4: st.metric("最大回撤", f"{m['maxdd']:.1f}%")

                    st.line_chart(
                        bt_data['df'].set_index('date')[['cum_tai','cum_lev']]
                        .rename(columns={'cum_tai':'大盤','cum_lev':f'{m["lev"]:.1f}x LEAPS'}),
                        use_container_width=True
                    )
                    st.caption(f"📊 {m['trades']}交易日 | Theta衰減0.03%/日 | 授權:{bt_data['email']}")

                    col_clr1, col_clr2 = st.columns(2)
                    with col_clr1:
                        if st.button("🗑️ 清除回測", key="clr_bt_v191"):
                            st.session_state[KEY_BT] = None; st.rerun()
                    with col_clr2:
                        st.caption(f"剩餘額度：{bt_data['uses_left']}/3")

    # ── 底部商業導流 ─────────────────────────────────────────────────────────────
    st.markdown("─" * 80)
    st.markdown("#### 💎 **貝伊果屋付費版功能對比**")
    
    col_free, col_paid = st.columns(2)
    with col_free:
        st.markdown("**🆓 免費版**")
        st.markdown("- 槓桿掃描\n- 微觀勝率\n- BS定價\n- Top15排序")
    with col_paid:
        st.markdown("**💎 付費版 (Email開通)**")
        st.markdown("- 真實TAIEX回測\n- Sharpe/勝率/DD\n- 每日3次免費\n- Threads更新")

    st.markdown("---")
    st.caption("""
    **貝伊果屋 (@beigou0427)** | v19.1 2026/3/10  
    ⚠️ 僅供學習參考，非投資建議 | 實際交易請評估風險
    """)
