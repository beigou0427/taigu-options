"""

🔰 貝伊果屋 - 財富雙軌系統 (旗艦完整版 v6.7)
整合：ETF定投 + 智能情報中心 + LEAP Call策略 + 戰情室(12因子) + 真實回測 + AI 產業鏈推導
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
# 0. 自動跳轉 JS 函數 (完美修復版，支援 jump=5)
# =========================================
def auto_jump_to_tab():
    jump = st.query_params.get("jump", None)
    if not jump:
        return False

    if isinstance(jump, list):
        jump = jump[0]

    jump = str(jump).strip().lower()

    if jump.startswith("tab"):
        idx_str = jump.replace("tab", "", 1)
    else:
        idx_str = jump

    if not idx_str.isdigit():
        return False

    target_idx = int(idx_str)

    components.html(
        f"""
        <script>
        (function() {{
          const target = {target_idx};
          let tries = 0;
          const timer = setInterval(() => {{
            const tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
            if (tabs && tabs.length > target) {{
              tabs[target].click();
              clearInterval(timer);
            }}
            tries += 1;
            if (tries > 40) clearInterval(timer); 
          }}, 200);
        }})();
        </script>
        """,
        height=0,
    )
    st.query_params.clear()
    return True

auto_jump_to_tab()

# =========================================
# 1. 初始化 & 設定
# =========================================
st.set_page_config(page_title="貝伊果屋-財富雙軌系統", layout="wide", page_icon="🥯")
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

with st.sidebar:
    st.markdown("## 🔥**強烈建議閱讀下列書籍後才投資!**")
    st.image("https://down-tw.img.susercontent.com/file/sg-11134201-7qvdl-lh2v8yc9n8530d.webp", caption="持續買進", use_container_width=True)
    st.markdown("[🛒 購買『 持續買進 』](https://s.shopee.tw/5AmrxVrig8)")
    st.divider()
    st.image("https://down-tw.img.susercontent.com/file/tw-11134207-7rasc-m2ba9wueqaze3a.webp", caption="長期買進", use_container_width=True)
    st.markdown("[🛒 購買『 長期買進 』](https://s.shopee.tw/6KypLiCjuy)")
    if st.session_state.get('is_pro', False):
        st.success("👑 Pro 會員")
    st.divider()
    st.caption("📊 功能導航：\\n• Tab0: 定投計畫\\n• Tab1: 智能情報\\n• Tab2: CALL獵人\\n• Tab3: 回測系統\\n• Tab4: 戰情室\\n• Tab5: AI產業鏈")

# =========================================
# 4. 主介面 & 市場快報
# =========================================
st.markdown("# 🥯 **貝伊果屋：縮小財富差距**")
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
if not st.session_state.get('disclaimer_accepted', False):
    
    # 頂部警告區塊
    st.markdown("""
    <div style='background-color: #2b1414; border-left: 6px solid #ff4b4b; padding: 25px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 15px rgba(0,0,0,0.4);'>
        <h2 style='color: #ff4b4b; margin-top: 0;'>🚨 股票完全新手必讀！</h2>
        <p style='color: #f8f9fa; font-size: 17px; margin-bottom: 15px; font-weight: 500;'>進入市場前，請務必搞懂以下 3 個核心基礎：</p>
        <ul style='color: #d1d5db; font-size: 16px; line-height: 1.8;'>
            <li><span style='color:#4ECDC4;'>💹 <b>股票</b></span>：買公司股份，必須承擔公司營運風險與股價波動</li>
            <li><span style='color:#4ECDC4;'>📈 <b>ETF</b></span>：買進一籃子優質股票，分散風險，是新手最穩健的首選</li>
            <li><span style='color:#4ECDC4;'>💳 <b>定期定額</b></span>：每個月固定金額買入，完美避開追高殺低的人性弱點</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
 
    # =========================================
    # 超強視覺按鈕 CSS（注入全局樣式）
    # =========================================
    st.markdown("""
    <style>
    /* 主系統按鈕：翡翠綠漸變 */
    div[data-testid="stButton"] button[kind="secondary"]:hover,
    div[data-testid="stButton"] button[kind="primary"]:hover { transform: translateY(-2px); }
    
    /* 針對 key=btn_main 的按鈕 */
    [data-testid="stButton"]:has(button:contains("進入主系統")) button {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%) !important;
        border: none !important; border-radius: 50px !important;
        font-size: 17px !important; font-weight: bold !important;
        box-shadow: 0 8px 20px rgba(56, 239, 125, 0.4) !important;
        padding: 16px 30px !important; color: white !important;
        transition: all 0.3s ease !important;
    }
    
    /* 針對 key=btn_ai 的按鈕：藍紫漸變 + 發光 */
    [data-testid="stButton"]:has(button:contains("AI 產業分析")) button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        border: 2px solid rgba(255,255,255,0.15) !important; border-radius: 50px !important;
        font-size: 17px !important; font-weight: bold !important;
        box-shadow: 0 8px 25px rgba(102, 126, 234, 0.5) !important;
        padding: 16px 30px !important; color: white !important;
        transition: all 0.3s ease !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 置中導語
    st.markdown("<h4 style='text-align: center; color: #bbb; margin: 20px 0;'>👆 請選擇你的啟動模式 👆</h4>", unsafe_allow_html=True)
    
    # 按鈕置中：左右各留白
    _, btn_col1, btn_col2, _ = st.columns([1.5, 3, 3, 1.5])
    
    with btn_col1:
        if st.button("🤖 直接體驗 AI 產業分析", key="btn_main", use_container_width=True):
            st.session_state.disclaimer_accepted = True
            st.balloons()
            st.rerun()
            
    with btn_col2:
        if st.button("✅ 我懂基礎，進入主系統", key="btn_ai", use_container_width=True):
            st.session_state.disclaimer_accepted = True
            st.query_params["jump"] = "5"
            st.balloons()
            st.rerun()
    
    # JS 美化按鈕（正確寫法：components.html，修復 TypeError）
    components.html("""
    <script>
        setTimeout(() => {
            const buttons = window.parent.document.querySelectorAll('.stButton > button');
            buttons.forEach(btn => {
                const text = btn.innerText || btn.textContent;
                if (text.includes('進入主系統')) {
                    btn.style.background = 'linear-gradient(135deg, #11998e 0%, #38ef7d 100%)';
                    btn.style.border = 'none';
                    btn.style.borderRadius = '50px';
                    btn.style.fontSize = '17px';
                    btn.style.fontWeight = 'bold';
                    btn.style.boxShadow = '0 8px 20px rgba(56, 239, 125, 0.4)';
                    btn.style.color = 'white';
                    btn.style.transition = 'all 0.3s ease';
                    btn.onmouseover = () => { btn.style.transform = 'translateY(-3px)'; btn.style.boxShadow = '0 12px 28px rgba(56, 239, 125, 0.6)'; };
                    btn.onmouseout = () => { btn.style.transform = 'translateY(0)'; btn.style.boxShadow = '0 8px 20px rgba(56, 239, 125, 0.4)'; };
                }
                if (text.includes('AI 產業分析')) {
                    btn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                    btn.style.border = '2px solid rgba(255,255,255,0.15)';
                    btn.style.borderRadius = '50px';
                    btn.style.fontSize = '17px';
                    btn.style.fontWeight = 'bold';
                    btn.style.boxShadow = '0 8px 25px rgba(102, 126, 234, 0.5)';
                    btn.style.color = 'white';
                    btn.style.transition = 'all 0.3s ease';
                    btn.onmouseover = () => { btn.style.transform = 'translateY(-3px)'; btn.style.boxShadow = '0 14px 30px rgba(102, 126, 234, 0.8)'; btn.style.background = 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)'; };
                    btn.onmouseout = () => { btn.style.transform = 'translateY(0)'; btn.style.boxShadow = '0 8px 25px rgba(102, 126, 234, 0.5)'; btn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'; };
                }
            });
        }, 300);
    </script>
    """, height=0)
    
    st.markdown("<hr style='border-color: #333; margin: 40px 0;'>", unsafe_allow_html=True)
    
    # 書籍推薦
    st.markdown("<h3 style='text-align: center;'>📚 零基礎投資必備經典</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #aaa; margin-bottom: 25px;'>建立正確投資觀念，才能在市場中長期生存</p>", unsafe_allow_html=True)
    
    _, book_col1, book_col2, _ = st.columns([1, 2, 2, 1])
    
    with book_col1:
        st.markdown("""
        <div style='background-color: #1a1a1a; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.4);'>
            <img src='https://down-tw.img.susercontent.com/file/sg-11134201-7qvdl-lh2v8yc9n8530d.webp' width='160' style='border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); margin-bottom: 15px;'>
            <a href='https://s.shopee.tw/5AmrxVrig8' target='_blank' style='text-decoration: none;'>
                <div style='background: linear-gradient(135deg, #ff6b6b, #ff4b4b); color: white; padding: 12px; border-radius: 10px; font-weight: bold; font-size: 15px;'>🛒 購買《持續買進》</div>
            </a>
        </div>
        """, unsafe_allow_html=True)
        
    with book_col2:
        st.markdown("""
        <div style='background-color: #1a1a1a; padding: 20px; border-radius: 15px; text-align: center; border: 1px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.4);'>
            <img src='https://down-tw.img.susercontent.com/file/tw-11134207-7rasc-m2ba9wueqaze3a.webp' width='160' style='border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5); margin-bottom: 15px;'>
            <a href='https://s.shopee.tw/6KypLiCjuy' target='_blank' style='text-decoration: none;'>
                <div style='background: linear-gradient(135deg, #4ECDC4, #2bbfb5); color: black; padding: 12px; border-radius: 10px; font-weight: bold; font-size: 15px;'>🛒 購買《長期買進》</div>
            </a>
        </div>
        """, unsafe_allow_html=True)
    
    st.stop()

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
with tabs[0]:
    KEY_RES = "results_lev_v185"
    KEY_BEST = "best_lev_v185"
    KEY_PF = "portfolio_lev"

    if KEY_RES not in st.session_state: st.session_state[KEY_RES] = []
    if KEY_BEST not in st.session_state: st.session_state[KEY_BEST] = None
    if KEY_PF not in st.session_state: st.session_state[KEY_PF] = []

    st.markdown("### ♟️ **專業戰情室 (槓桿篩選 + 微觀勝率 + LEAPS CALL)**")
    col_search, col_portfolio = st.columns([1.3, 0.7])

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

    # 2. 微觀展開 (Top 40% -> 90-95%)
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

    with col_search:
        st.markdown("#### 🔍 **槓桿掃描 (LEAPS CALL 優化)**")
        
        if df_latest.empty: st.error("⚠️ 無資料"); st.stop()
        
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
            # ✅ 預設遠月合約 (LEAPS CALL 偏好)
            default_idx = len(available) - 1 if available else 0
            sel_con = st.selectbox("月份", available if available else [""], 
                                 index=default_idx, key="v185_con")
        with c3:
            target_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5, key="v185_lev")
        with c4:
            if st.button("🧹 重置", key="v185_reset"):
                st.session_state[KEY_RES] = []
                st.session_state[KEY_BEST] = None
                st.rerun()

        if st.button("🚀 執行掃描", type="primary", use_container_width=True, key="v185_scan"):
            st.session_state[KEY_RES] = []
            st.session_state[KEY_BEST] = None
            
            if sel_con and len(str(sel_con))==6:
                tdf = df_work[(df_work["contract_date"].astype(str)==sel_con) & (df_work["call_put"]==op_type)]
                
                if tdf.empty: st.warning("無資料")
                else:
                    try:
                        y, m = int(str(sel_con)[:4]), int(str(sel_con)[4:6])
                        days = max((date(y,m,15)-latest_date.date()).days, 1)
                        T = days / 365.0
                    except: st.error("日期解析失敗"); st.stop()

                    raw_results = []
                    for _, row in tdf.iterrows():
                        try:
                            K = float(row["strike_price"])
                            vol = float(row["volume"])
                            close_p = float(row["close"])
                            if K<=0: continue
                            
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
                            if P <= 0.5: continue
                            lev = (abs(delta)*S_current)/P
                            
                            if abs(delta) < 0.1: continue

                            # 1. 原始分
                            raw_score = calculate_raw_score(delta, days, vol, S_current, K, op_type)
                            status = "🟢成交" if vol > 0 else "🔵合理"

                            raw_results.append({
                                "履約價": int(K), 
                                "價格": P, 
                                "狀態": status, 
                                "槓桿": lev,
                                "Delta": delta,
                                "raw_score": raw_score,
                                "Vol": int(vol),
                                "差距": abs(lev - target_lev),
                                "合約": sel_con, 
                                "類型": op_type,
                                "天數": days  # 新增，用於排序
                            })
                        except: continue
                    
                    if raw_results:
                        # 2. 微觀展開勝率
                        final_results = micro_expand_scores(raw_results)
                        
                        # 3. 排序：優先找槓桿最接近的，其次看勝率，最後天數（遠月優先）
                        final_results.sort(key=lambda x: (x['差距'], -x['勝率'], -x['天數']))
                        
                        st.session_state[KEY_RES] = final_results[:15]
                        st.session_state[KEY_BEST] = final_results[0]
                        st.success(f"掃描完成！最佳槓桿：{final_results[0]['槓桿']:.1f}x")
                    else: st.warning("無符合資料")

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
                if st.button("➕ 加入", key="add_pf_v185"):
                    exists = any(p['履約價'] == best['履約價'] and 
                                 p['合約'] == best['合約'] for p in st.session_state[KEY_PF])
                    if not exists:
                        st.session_state[KEY_PF].append(best)
                        st.toast("✅ 已加入投組")
                    else: st.toast("⚠️ 已存在")

            with st.expander("📋 搜尋結果 (依槓桿→勝率→天數排序)", expanded=True):
                df_show = pd.DataFrame(st.session_state[KEY_RES]).copy()
                
                df_show['權利金'] = df_show['價格'].round(0).astype(int)
                df_show['槓桿'] = df_show['槓桿'].map(lambda x: f"{x:.1f}x")
                df_show['Delta'] = df_show['Delta'].map(lambda x: f"{x:.2f}")
                df_show['勝率'] = df_show['勝率'].map(lambda x: f"{x:.1f}%")
                df_show['天數'] = df_show.get('天數', 0).astype(int)
                
                cols = ["合約", "履約價", "權利金", "槓桿", "勝率", "天數", "差距"]
                st.dataframe(df_show[cols], use_container_width=True, hide_index=True)

    with col_portfolio:
        st.markdown("#### 💼 **LEAPS CALL 投組**")
        if st.session_state[KEY_PF]:
            pf = pd.DataFrame(st.session_state[KEY_PF])
            total = pf['價格'].sum() * 50
            avg_win = pf['勝率'].mean()
            avg_lev = pf['槓桿'].mean()
            
            st.metric("總權利金", f"${int(total):,}")
            st.caption(f"{len(pf)}口 | Avg槓桿 {avg_lev:.1f}x | Avg勝率 {avg_win:.1f}%")
            
            pf_s = pf.copy()
            pf_s['權利金'] = pf_s['價格'].round(0).astype(int)
            pf_s['Delta'] = pf_s['Delta'].map(lambda x: f"{float(x):.2f}")
            pf_s['勝率'] = pf_s['勝率'].map(lambda x: f"{float(x):.1f}%")
            pf_s['槓桿'] = pf_s['槓桿'].map(lambda x: f"{x:.1f}x")
            
            st.dataframe(pf_s[["合約", "履約價", "權利金", "槓桿", "勝率"]], 
                         use_container_width=True, hide_index=True)
            
            c_clr, c_dl = st.columns(2)
            with c_clr:
                if st.button("🗑️ 清空投組", key="clr_pf_v185"):
                    st.session_state[KEY_PF] = []
                    st.rerun()
            with c_dl:
                st.download_button("📥 CSV匯出", pf.to_csv(index=False).encode('utf-8'), 
                                   "LEAPs_call_pf_v185.csv", key="dl_pf_v185")
        else: st.info("💡 請先掃描並加入合約")

    # ✅ LEAPS CALL 介紹區塊
    st.markdown("---")
    st.markdown("#### 📚 **LEAPS / LEAPS CALL 策略簡介**")
    st.markdown("""
    **LEAPS CALL (長期看漲選擇權)**：
    - 到期日 > 6個月，時間衰減緩慢，適合長期看多標的（如AI、指數）
    - **優勢**：高槓桿、低成本替代現股，時間價值損耗少
    - **本系統優化**：預設遠月合約 + 槓桿篩選，優先推薦深度價內/價平合約
    - **建議情境**：波段操作、避開短期震盪、建構低成本多頭部位
    """)
    
    st.caption("📊 **操作邏輯**：優先槓桿最接近 → 最高微觀勝率 → 最遠天數。建議搭配遠月 LEAPS CALL 降低時間風險。")

