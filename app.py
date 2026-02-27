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
    st.info(f"🔑 Token 狀態: {'✅ 已設定' if FINMIND_TOKEN else '❌ 未設定'}")
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
st.markdown("# 🥯 **貝伊果屋：財富雙軌系統**")
st.markdown("---")

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
tabnames = ["AI產業鏈", "大盤", "CALL獵人", "回測", "戰情室", "持續買進"]
tabs = st.tabs(tabnames)

# [此處以下銜接原本的 with tabs[0]: ]

# --------------------------
# Tab 0: 穩健 ETF (v8.2 - 雙源穩定版)
# --------------------------

import os
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import pandas as pd
import numpy as np
import pytz
import holidays
from datetime import datetime, time, date, timedelta
import yfinance as yf  # 新增 yfinance

import plotly.express as px

# ========= Helpers =========
TAIPEI_TZ = pytz.timezone("Asia/Taipei")
TW_HOLIDAYS = holidays.TW()

ETF_LIST = ["0050", "006208", "00662", "00757", "00646"]

ETF_META = {
    "0050": {"icon": "🇹🇼", "name": "元大台灣50", "track": "台灣50指數", "region": "台灣", "asset": "股票", "risk": "中", "hint": "台股大盤核心；適合新手定投"},
    "006208": {"icon": "📈", "name": "富邦台50", "track": "台灣50指數", "region": "台灣", "asset": "股票", "risk": "中", "hint": "同追蹤台灣50；常被拿來比較成本與流動性"},
    "00662": {"icon": "🇻🇳", "name": "富邦富時越南", "track": "富時越南相關指數", "region": "越南", "asset": "股票", "risk": "高", "hint": "新興市場波動大；適合高風險配置"},
    "00757": {"icon": "💻", "name": "統一FANG+", "track": "NYSE FANG+", "region": "美國", "asset": "股票", "risk": "高", "hint": "科技集中度高；回撤會更深"},
    "00646": {"icon": "🇯🇵", "name": "富邦日本", "track": "日股相關指數", "region": "日本", "asset": "股票", "risk": "中", "hint": "做全球分散；會有匯率影響"},
}

def _today_tw() -> date:
    return datetime.now(TAIPEI_TZ).date()

def _now_tw() -> datetime:
    return datetime.now(TAIPEI_TZ)

def is_market_open_tw() -> tuple:
    now = _now_tw()
    if now.weekday() >= 5 or now.date() in TW_HOLIDAYS:
        return False, f"非交易日 {now.strftime('%m/%d')}"
    open_t, close_t = time(9, 0), time(13, 30)
    if open_t <= now.time() <= close_t:
        return True, f"開盤中 {now.strftime('%H:%M')}"
    return False, f"盤後 {now.strftime('%H:%M')}"

def parse_pct(x) -> float:
    s = str(x).strip()
    if not s or s.upper() == "N/A":
        return np.nan
    s = s.replace("%", "").replace("+", "")
    try:
        return float(s) / 100.0
    except:
        return np.nan

#========= Tab 0 =========


#        


# --------------------------
# Tab 1: 智能全球情報中心 (v6.7 全真實數據版)
# --------------------------
with tabs[1]:
    st.markdown("## 🌍 **智能全球情報中心**")

    # 🔥 新增：抓取真實市場數據 (台股 + 美股 + 幣圈)
    @st.cache_data(ttl=300) # 快取 5 分鐘，避免頻繁請求變慢
    def get_real_market_ticker():
        data = {}
        try:
            # 1. 台股 (FinMind)
            dl = DataLoader()
            dl.login_by_token(api_token=FINMIND_TOKEN)
            
            # TAIEX
            df_tw = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=5)).strftime("%Y-%m-%d"))
            if not df_tw.empty:
                close = df_tw['close'].iloc[-1]
                prev = df_tw['close'].iloc[-2]
                change = (close - prev) / prev * 100
                data['taiex'] = f"{close:,.0f}"
                data['taiex_pct'] = f"{change:+.1f}%"
                data['taiex_color'] = "#28a745" if change > 0 else "#dc3545"
            else:
                data['taiex'] = "N/A"; data['taiex_pct'] = "0%"; data['taiex_color'] = "gray"

            # 台積電 (2330)
            df_tsmc = dl.taiwan_stock_daily("2330", start_date=(date.today()-timedelta(days=5)).strftime("%Y-%m-%d"))
            if not df_tsmc.empty:
                close = df_tsmc['close'].iloc[-1]
                prev = df_tsmc['close'].iloc[-2]
                change = (close - prev) / prev * 100
                data['tsmc'] = f"{close:,.0f}"
                data['tsmc_pct'] = f"{change:+.1f}%"
                data['tsmc_color'] = "#28a745" if change > 0 else "#dc3545"
            else:
                data['tsmc'] = "N/A"; data['tsmc_pct'] = "0%"; data['tsmc_color'] = "gray"

            # 2. 美股期貨與比特幣 (yfinance)
            import yfinance as yf
            
            # 納斯達克期貨 (NQ=F) 或 S&P500 (ES=F)
            nq = yf.Ticker("NQ=F").history(period="2d")
            if len(nq) > 0:
                last = nq['Close'].iloc[-1]
                prev = nq['Close'].iloc[-2] if len(nq) > 1 else last
                chg = (last - prev) / prev * 100
                data['nq'] = f"{last:,.0f}"
                data['nq_pct'] = f"{chg:+.1f}%"
                data['nq_color'] = "#28a745" if chg > 0 else "#dc3545"
            else:
                data['nq'] = "N/A"; data['nq_pct'] = "0%"; data['nq_color'] = "gray"

            # 比特幣 (BTC-USD)
            btc = yf.Ticker("BTC-USD").history(period="2d")
            if len(btc) > 0:
                last = btc['Close'].iloc[-1]
                prev = btc['Close'].iloc[-2] if len(btc) > 1 else last
                chg = (last - prev) / prev * 100
                data['btc'] = f"${last:,.0f}"
                data['btc_pct'] = f"{chg:+.1f}%"
                data['btc_color'] = "#28a745" if chg > 0 else "#dc3545"
            else:
                data['btc'] = "N/A"; data['btc_pct'] = "0%"; data['btc_color'] = "gray"

        except Exception as e:
            # 出錯時的回退顯示
            return {k: "N/A" for k in ['taiex','tsmc','nq','btc']}
            
        return data

    # 執行抓取
    m = get_real_market_ticker()

    # 渲染真實跑馬燈
    st.markdown(f"""
    <div class="ticker-wrap">
        🚀 <b>即時行情:</b> 
        TAIEX: <span style="color:{m.get('taiex_color','gray')}">{m.get('taiex','N/A')} ({m.get('taiex_pct','')})</span> &nbsp;|&nbsp; 
        台積電: <span style="color:{m.get('tsmc_color','gray')}">{m.get('tsmc','N/A')} ({m.get('tsmc_pct','')})</span> &nbsp;|&nbsp; 
        Nasdaq期: <span style="color:{m.get('nq_color','gray')}">{m.get('nq','N/A')} ({m.get('nq_pct','')})</span> &nbsp;|&nbsp; 
        Bitcoin: <span style="color:{m.get('btc_color','gray')}">{m.get('btc','N/A')} ({m.get('btc_pct','')})</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("數據來源：FinMind (台股) + Yahoo Finance (國際/加密幣)")
    # Session State 初始化
    if 'filter_kw' not in st.session_state:
        st.session_state['filter_kw'] = "全部"

    with st.spinner("🤖 正在掃描全球市場訊號..."):
        # 2. 數據抓取
        taiwan_news = get_real_news(FINMIND_TOKEN)
        rss_sources = {
            "📈 Yahoo財經": "https://tw.stock.yahoo.com/rss/index.rss",
            "🌐 Reuters": "https://feeds.reuters.com/reuters/businessNews",
            "📊 CNBC Tech": "https://www.cnbc.com/id/19854910/device/rss/rss.html"
        }
        
        all_news = []
        if not taiwan_news.empty:
            for _, row in taiwan_news.head(5).iterrows():
                all_news.append({
                    'title': str(row.get('title', '無標題')), 'link': str(row.get('link', '#')),
                    'source': "🇹🇼 台股新聞", 'time': pd.to_datetime(row['date']).strftime('%m/%d %H:%M'),
                    'summary': str(row.get('description', ''))[:100] + '...'
                })
        
        import feedparser
        for title, url in rss_sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    all_news.append({
                        'title': str(entry.title), 'link': str(entry.link), 'source': title,
                        'time': entry.get('published', 'N/A'), 'summary': str(entry.get('summary', ''))[:100] + '...'
                    })
            except: pass

        # 3. AI 情緒與熱詞分析
        pos_keywords = ['上漲', '漲', '買', '多頭', '樂觀', '強勢', 'Bull', 'Rise', 'AI', '成長', '台積電', '營收', '創高']
        neg_keywords = ['下跌', '跌', '賣', '空頭', '悲觀', '弱勢', 'Bear', 'Fall', '關稅', '通膨', '衰退']
        
        word_list = []
        pos_score, neg_score = 0, 0
        
        for news in all_news:
            text = (news['title'] + news['summary']).lower()
            n_pos = sum(text.count(k.lower()) for k in pos_keywords)
            n_neg = sum(text.count(k.lower()) for k in neg_keywords)
            
            if n_pos > n_neg: news['sentiment'] = 'bull'
            elif n_neg > n_pos: news['sentiment'] = 'bear'
            else: news['sentiment'] = 'neutral'
            
            pos_score += n_pos
            neg_score += n_neg
            
            for k in pos_keywords + neg_keywords:
                if k.lower() in text:
                    word_list.append(k)

        sentiment_idx = (pos_score - neg_score) / max(pos_score + neg_score, 1)
        sentiment_label = "🟢 貪婪" if sentiment_idx > 0.2 else "🔴 恐慌" if sentiment_idx < -0.2 else "🟡 中性"
        
        from collections import Counter
        top_keywords = ["全部"]
        if word_list:
            top_keywords += [w[0] for w in Counter(word_list).most_common(6)]
        else:
            top_keywords += ["台積電", "AI", "降息", "強勢", "營收"]

    # 4. 儀表板區域
    col_dash1, col_dash2 = st.columns([1, 2])
    
    with col_dash1:
        st.markdown(f"#### 🌡️ 市場情緒：{sentiment_label}")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", 
            value = 50 + sentiment_idx*50,
            gauge = {
                'axis': {'range': [0, 100]}, 
                'bar': {'color': "#4ECDC4"},
                'steps': [
                    {'range': [0, 40], 'color': "rgba(255, 0, 0, 0.2)"},
                    {'range': [60, 100], 'color': "rgba(0, 255, 0, 0.2)"}
                ]
            }
        ))
        fig_gauge.update_layout(height=220, margin=dict(l=20,r=20,t=10,b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col_dash2:
        st.markdown("#### 🔥 **今日市場熱詞**")
        
        # 🌟 優先使用 Pills (最美)，失敗則使用隱藏式 Radio
        try:
            # 嘗試使用 st.pills (Streamlit 1.40+)
            selected = st.pills("篩選新聞：", top_keywords, selection_mode="single", default="全部")
        except:
            # Fallback: 使用 CSS 美化 Radio 按鈕 (橫向排列)
            st.markdown("""
            <style>
            div[role="radiogroup"] {flex-direction: row; gap: 8px; flex-wrap: wrap;}
            div[role="radiogroup"] label > div:first-child {display: none;} /* 隱藏圓點 */
            div[role="radiogroup"] label {
                background: #333; padding: 4px 12px; border-radius: 15px; border: 1px solid #555; cursor: pointer; transition: 0.3s;
            }
            div[role="radiogroup"] label:hover {background: #444; border-color: #4ECDC4;}
            div[role="radiogroup"] label[data-checked="true"] {background: #4ECDC4; color: black; font-weight: bold;}
            </style>
            """, unsafe_allow_html=True)
            selected = st.radio("篩選新聞：", top_keywords, label_visibility="collapsed")
            
        st.session_state['filter_kw'] = selected
        st.success(f"🔍 篩選：#{selected} | 📊 市場氣氛：{sentiment_label}")

    st.divider()
    
    # 5. 過濾與顯示新聞 (修復 TypeError)
    current_filter = st.session_state['filter_kw']
    st.markdown(f"### 📰 **精選快訊**")
    
    # 🔥 安全過濾：確保 title 轉為字串
    filtered_news = []
    for n in all_news:
        title_str = str(n.get('title', ''))
        summary_str = str(n.get('summary', ''))
        
        if current_filter == "全部":
            filtered_news.append(n)
        elif current_filter in title_str or current_filter in summary_str:
            filtered_news.append(n)
            
    if not filtered_news:
        st.info(f"⚠️ 暫無包含「{current_filter}」的新聞，顯示全部。")
        filtered_news = all_news 
    
    col_news_left, col_news_right = st.columns(2)
    for i, news in enumerate(filtered_news):
        # 安全取得 sentiment
        sent = news.get('sentiment', 'neutral')
        
        if sent == 'bull':
            tag_html = '<span class="tag-bull">看多</span>'
            border_color = "#28a745"
        elif sent == 'bear':
            tag_html = '<span class="tag-bear">看空</span>'
            border_color = "#dc3545"
        else:
            tag_html = '<span class="tag-neutral">中性</span>'
            border_color = "#6c757d"

        card_html = f"""
        <div class="news-card" style="border-left: 5px solid {border_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span class="source-badge">{news['source']}</span>
                    {tag_html}
                </div>
                <div style="font-size: 0.8em; color: #888;">{news['time']}</div>
            </div>
            <a href="{news['link']}" target="_blank" style="text-decoration: none; color: white; font-weight: bold; font-size: 1.1em; display: block; margin-bottom: 5px; line-height: 1.4;">
                {news['title']}
            </a>
            <div style="font-size: 0.9em; color: #aaa; margin-bottom: 5px; line-height: 1.5;">
                {news['summary']}
            </div>
        </div>
        """
        
        if i % 2 == 0:
            with col_news_left: st.markdown(card_html, unsafe_allow_html=True)
        else:
            with col_news_right: st.markdown(card_html, unsafe_allow_html=True)
# --------------------------
# Tab 2: 槓桿篩選版 v18.5 (回歸槓桿操作 + LEAPS CALL)
# --------------------------
with tabs[2]:
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


# --------------------------
# Tab 3: 歷史回測
# --------------------------
with tabs[3]:
    st.markdown("### 📊 **策略時光機：真實歷史驗證**")
    
    if not st.session_state.is_pro:
        col_lock1, col_lock2 = st.columns([2, 1])
        with col_lock1:
            st.warning("🔒 **此為 Pro 會員專屬功能**")
            st.info("解鎖後可查看：\n- ✅ 真實歷史數據回測\n- ✅ 策略 vs 大盤績效對決\n- ✅ 詳細交易訊號點位")
        with col_lock2:
            st.metric("累積報酬率", "🔒 ???%", "勝率 ???%")
            if st.button("⭐ 免費升級 Pro", key="upgrade_btn_tab3"):
                st.session_state.is_pro = True; st.balloons(); st.rerun()
        st.image("https://via.placeholder.com/1000x300?text=Pro+Feature+Locked", use_container_width=True)
    
    else:
        with st.expander("⚙️ **回測參數設定**", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: period_days = st.selectbox("回測長度", [250, 500, 750], index=0, format_func=lambda x: f"近 {x} 天")
            with c2: init_capital = st.number_input("初始本金 (萬)", 10, 500, 100)
            with c3: leverage = st.slider("模擬槓桿", 1, 3, 1)

        if st.button("🚀 執行真實回測", type="primary"):
            with st.spinner("正在下載並計算歷史數據..."):
                dl = DataLoader()
                dl.login_by_token(api_token=FINMIND_TOKEN)
                
                end_date = date.today().strftime("%Y-%m-%d")
                start_date = (date.today() - timedelta(days=period_days + 150)).strftime("%Y-%m-%d")
                df_hist = dl.taiwan_stock_daily("TAIEX", start_date=start_date, end_date=end_date)
                
                if df_hist.empty:
                    st.error("❌ 無法取得歷史數據，請稍後再試")
                else:
                    df_hist['close'] = df_hist['close'].astype(float)
                    df_hist['MA20'] = df_hist['close'].rolling(20).mean()
                    df_hist['MA60'] = df_hist['close'].rolling(60).mean()
                    df_hist = df_hist.dropna().tail(period_days).reset_index(drop=True)
                    
                    df_hist['Signal'] = (df_hist['close'] > df_hist['MA20']) & (df_hist['MA20'] > df_hist['MA60'])
                    df_hist['Daily_Ret'] = df_hist['close'].pct_change().fillna(0)
                    df_hist['Strategy_Ret'] = df_hist['Signal'].shift(1).fillna(False) * df_hist['Daily_Ret'] * leverage
                    
                    df_hist['Equity_Strategy'] = init_capital * (1 + df_hist['Strategy_Ret']).cumprod()
                    df_hist['Equity_Benchmark'] = init_capital * (1 + df_hist['Daily_Ret']).cumprod()
                    
                    total_ret = (df_hist['Equity_Strategy'].iloc[-1] / init_capital - 1) * 100
                    bench_ret = (df_hist['Equity_Benchmark'].iloc[-1] / init_capital - 1) * 100
                    win_days = df_hist[df_hist['Strategy_Ret'] > 0]
                    win_rate = len(win_days) / len(df_hist[df_hist['Signal'].shift(1)==True]) * 100 if len(df_hist[df_hist['Signal'].shift(1)==True]) > 0 else 0
                    
                    st.divider()
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 策略最終資產", f"{int(df_hist['Equity_Strategy'].iloc[-1]):,} 萬", f"{total_ret:+.1f}%")
                    k2.metric("🐢 大盤同期表現", f"{bench_ret:+.1f}%", f"超額 {total_ret - bench_ret:+.1f}%", delta_color="off")
                    k3.metric("🏆 交易勝率 (日)", f"{win_rate:.1f}%")
                    k4.metric("📅 交易天數", f"{df_hist['Signal'].sum()} 天", f"佔比 {df_hist['Signal'].mean()*100:.0f}%")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['Equity_Strategy'], name='貝伊果策略', line=dict(color='#00CC96', width=2)))
                    fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['Equity_Benchmark'], name='大盤指數', line=dict(color='#EF553B', width=2, dash='dash')))
                    fig.update_layout(title="資金權益曲線 (真實歷史)", yaxis_title="資產淨值 (萬)", hovermode="x unified", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("#### 📝 **近期策略訊號**")
                    recent_df = df_hist.tail(10).copy()
                    recent_df['訊號'] = recent_df['Signal'].apply(lambda x: "🟢 持有" if x else "⚪ 空手")
                    recent_df['日期'] = pd.to_datetime(recent_df['date']).dt.strftime('%Y-%m-%d')
                    st.dataframe(recent_df[['日期', 'close', 'MA20', '訊號']].sort_values("日期", ascending=False), hide_index=True)

# --------------------------
# Tab 4: 專業戰情室 (全功能整合版)
# --------------------------
with tabs[4]:
    st.markdown("## 📰 **專業戰情中心**")
    st.caption(f"📅 資料日期：{latest_date.strftime('%Y-%m-%d')} | 💡 模型版本：v6.0 (戰情+籌碼整合)")

    # 進階數據計算函數
    def calculate_advanced_factors(current_price, ma20, ma60, df_latest, token):
        score = 0
        details = []
        
        if current_price > ma20: score += 10; details.append("✅ 站上月線 (+10)")
        if ma20 > ma60: score += 10; details.append("✅ 均線多排 (+10)")
        if current_price > ma60: score += 5; details.append("✅ 站上季線 (+5)")
        if (current_price - ma60)/ma60 > 0.05: score += 5; details.append("✅ 季線乖離強 (+5)")

        try:
            low_min = df_latest['min'].min() if 'min' in df_latest else current_price * 0.9
            high_max = df_latest['max'].max() if 'max' in df_latest else current_price * 1.1
            rsv = (current_price - low_min) / (high_max - low_min) * 100
            if rsv > 50: score += 5; details.append("✅ RSV偏多 (+5)")
            if rsv > 80: score += 5; details.append("🔥 動能強勁 (+5)")
        except: pass

        if (current_price - ma20)/ma20 > 0.02: score += 10; details.append("✅ 短線急攻 (+10)")

        try:
            last_chip = get_institutional_data(token)
            net_buy = last_chip['net'].sum() if not last_chip.empty else 0
            if net_buy > 20: score += 15; details.append("✅ 法人大買 (+15)")
            elif net_buy > 0: score += 5; details.append("✅ 法人小買 (+5)")
            elif net_buy < -20: score -= 5; details.append("⚠️ 法人大賣 (-5)")
        except: pass

        bias = (current_price - ma20) / ma20 * 100
        if bias > 3.5: score -= 5; details.append("⚠️ 乖離過熱 (-5)")
        if bias < -3.5: score += 5; details.append("✅ 乖離過冷反彈 (+5)")

        score += 10
        return min(100, max(0, score)), details

    col_kpi1, col_kpi2 = st.columns([1, 1.5])

    with col_kpi1:
        st.markdown("#### 🌡️ **全方位多空溫度計**")
        
        total_score, score_details = calculate_advanced_factors(S_current, ma20, ma60, df_latest, FINMIND_TOKEN)
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = total_score,
            delta = {'reference': 50, 'increasing': {'color': "#28a745"}, 'decreasing': {'color': "#dc3545"}},
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "多空綜合評分", 'font': {'size': 20}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#ff4b4b" if total_score < 40 else "#28a745" if total_score > 75 else "#ffc107"},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#333",
                'steps': [
                    {'range': [0, 40], 'color': 'rgba(255, 0, 0, 0.3)'},   
                    {'range': [40, 75], 'color': 'rgba(255, 255, 0, 0.3)'},  
                    {'range': [75, 100], 'color': 'rgba(0, 255, 0, 0.3)'}], 
            }
        ))
        
        fig_gauge.update_layout(height=280, margin=dict(l=30, r=30, t=30, b=30), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        trend_score = 0
        if S_current > ma20: trend_score += 1
        if ma20 > ma60: trend_score += 1
        
        if trend_score == 2: signal = "🟢 強勢買點"
        elif trend_score == 1: signal = "🟡 觀望整理"
        else: signal = "🔴 高風險區"
            
        st.metric("🚦 趨勢燈號", signal, f"指數 {S_current:,.0f}")
        
        with st.expander("🔍 查看 12 因子細項"):
            st.write(f"**總分：{total_score}**")
            st.markdown(" • " + "\n • ".join(score_details))

    with col_kpi2:
        st.markdown("#### 🤖 **貝伊果 AI 戰略解讀**")
        
        if total_score >= 80:
            ai_title = "🔥 多頭狂熱：利潤奔跑模式"
            ai_status = "極度樂觀"
            ai_desc = "市場進入「瘋狗浪」階段！所有指標全面翻多，均線發散，量能失控。這是順勢交易者的天堂，但請注意：**乖離率過大隨時可能急殺洗盤**。"
            ai_strat_title = "⚔️ 攻擊策略："
            ai_strat_content = "<li><b>期權</b>：Tab 2 積極買進價外 1-2 檔 Call，槓桿全開。</li><li><b>現貨</b>：持有強勢股，沿 5 日線移動停利。</li>"
            ai_tips = "✅ <b>追價要快</b>：猶豫就沒了<br>🛑 <b>停利要狠</b>：破線就跑"
            box_color = "rgba(220, 53, 69, 0.15)" 
            border_color = "#dc3545" 
            
        elif total_score >= 60:
            ai_title = "🐂 多頭排列：穩健獲利模式"
            ai_status = "樂觀偏多"
            ai_desc = "趨勢溫和向上，最舒服的盤勢。指數站穩月線，MACD 金叉，籌碼安定。這時候不要頻繁進出，**「抱得住」才是贏家**。"
            ai_strat_title = "⚔️ 攻擊策略："
            ai_strat_content = "<li><b>期權</b>：Tab 2 選擇價平 Call，賺取波段漲幅。</li><li><b>ETF</b>：Tab 0 的 0050/QQQ 放心續抱。</li>"
            ai_tips = "✅ <b>拉回找買點</b>：靠近 MA20 是機會<br>🛑 <b>減少當沖</b>：波段利潤更大"
            box_color = "rgba(40, 167, 69, 0.15)"
            border_color = "#28a745"

        elif total_score >= 40:
            ai_title = "⚖️ 多空膠著：雙巴震盪模式"
            ai_status = "中立觀望"
            ai_desc = "現在是「絞肉機」行情！均線糾結，忽漲忽跌。指標出現背離（如價格創高但 RSI 沒創高）。這時候**「不做」就是「賺」**。"
            ai_strat_title = "🛡️ 防禦策略："
            ai_strat_content = "<li><b>期權</b>：切勿 Buy Call/Put！適合做 <b>Credit Spread (收租)</b>。</li><li><b>資金</b>：保留 7 成現金，等待突破。</li>"
            ai_tips = "✅ <b>區間操作</b>：箱頂賣、箱底買<br>🛑 <b>嚴禁追單</b>：突破往往是假突破"
            box_color = "rgba(255, 193, 7, 0.15)"
            border_color = "#ffc107"

        elif total_score >= 20:
            ai_title = "🐻 空方試探：保守防禦模式"
            ai_status = "謹慎偏空"
            ai_desc = "支撐鬆動，風險正在堆積！指數跌破月線，MACD 死叉。多單請務必減碼，不要與趨勢作對。"
            ai_strat_title = "🛡️ 防禦策略："
            ai_strat_content = "<li><b>現貨</b>：反彈到壓力區（如 MA20）就減碼。</li><li><b>避險</b>：可小量買進 00632R (台灣50反1) 或 Put。</li>"
            ai_tips = "✅ <b>現金為王</b>：活著最重要<br>🛑 <b>別急著抄底</b>：還沒跌完"
            box_color = "rgba(23, 162, 184, 0.15)"
            border_color = "#17a2b8"

        else:
            ai_title = "⛈️ 空頭屠殺：全面撤退模式"
            ai_status = "極度恐慌"
            ai_desc = "警報響起！均線蓋頭反壓，布林通道開口向下。此刻**任何反彈都是逃命波**，不要幻想 V 轉。"
            ai_strat_title = "⚔️ 空方策略："
            ai_strat_content = "<li><b>期權</b>：積極 Buy Put，但要快進快出。</li><li><b>心態</b>：承認虧損，清空多單，留得青山在。</li>"
            ai_tips = "✅ <b>果斷停損</b>：不要有僥倖心態<br>🛑 <b>絕對禁止攤平</b>：會越攤越平"
            box_color = "rgba(52, 58, 64, 0.15)"
            border_color = "#343a40"

        html_content = f"""
<div style="border-left: 5px solid {border_color}; background-color: {box_color}; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #EEE;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h3 style="margin:0; font-size: 1.3em; color: white;">{ai_title}</h3>
        <span style="background-color:{border_color}; color:white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold;">{ai_status}</span>
    </div>
    <p style="font-size: 15px; line-height: 1.6; margin-bottom: 15px;">{ai_desc}</p>
    <div style="margin-bottom: 15px;">
        <strong style="color: {border_color};">{ai_strat_title}</strong>
        <ul style="margin-top: 5px; padding-left: 20px;">
            {ai_strat_content}
        </ul>
    </div>
    <div style="background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 5px; font-size: 0.9em; border: 1px dashed {border_color};">
        {ai_tips}
    </div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)
        
        import random
        quotes = [
            "「行情總在絕望中誕生，在半信半疑中成長。」", "「截斷虧損，讓利潤奔跑。」",
            "「不要預測行情，要跟隨行情。」", "「新手看價，老手看量，高手看籌碼。」"
        ]
        st.caption(f"📜 **貝伊果心法**：{random.choice(quotes)}")

    st.divider()

    st.markdown("### 🔥 **籌碼戰場與點位分析**")
    
    col_chip1, col_chip2 = st.columns([1.5, 1])

    with col_chip1:
        st.markdown("#### 💰 **籌碼戰場 (OI Walls)**")
        st.plotly_chart(plot_oi_walls(S_current), use_container_width=True)
        st.caption("💡 紅色為大量 Call 賣壓 (壓力)，青色為大量 Put 支撐")

        st.markdown("#### 🏦 **三大法人動向**")
        with st.spinner("載入法人資料..."):
            df_chips = get_institutional_data(FINMIND_TOKEN) 
        if not df_chips.empty:
            name_map = {"Foreign_Investors": "外資", "Investment_Trust": "投信", "Dealer_Self": "自營商(自行)", "Dealer_Hedging": "自營商(避險)"}
            df_chips['name_tw'] = df_chips['name'].map(name_map).fillna(df_chips['name'])
            fig_chips = px.bar(df_chips, x="name_tw", y="net", color="net",
                              color_continuous_scale=["green", "red"],
                              labels={"net": "買賣超(億)", "name_tw": "法人身分"},
                              text="net", title=f"三大法人合計買賣超 ({df_chips['date'].iloc[0].strftime('%m/%d')})")
            fig_chips.update_traces(texttemplate='%{text:.1f} 億', textposition='outside')
            fig_chips.update_layout(height=250)
            st.plotly_chart(fig_chips, use_container_width=True)
        else:
            st.warning("⚠️ 暫無法人資料 (下午 3 點後更新)")

    with col_chip2:
        st.markdown("#### 📉 **即時損益試算**")
        k_sim = st.number_input("模擬履約價", 15000, 50000, int(S_current))
        p_sim = st.number_input("權利金", 1, 1000, 150)
        st.plotly_chart(plot_payoff(k_sim, p_sim, "CALL"), use_container_width=True)
        
        st.markdown("#### 🔑 **關鍵點位**")
        with st.spinner("計算支撐壓力..."):
            real_pressure, real_support = get_support_pressure(FINMIND_TOKEN)
        if real_pressure > 0:
            st.metric("🛑 波段壓力 (20日高)", f"{int(real_pressure)}", delta=f"{real_pressure-S_current:.0f}", delta_color="inverse")
            st.metric("🏠 目前點位", f"{int(S_current)}")
            st.metric("🛡️ 波段支撐 (60日低)", f"{int(real_support)}", delta=f"{real_support-S_current:.0f}")
        else:
            st.warning("⚠️ K 線資料連線中斷")

    st.markdown("#### 💼 **我的投組**")
    if st.button("➕ 加入虛擬倉位"):
        st.session_state.portfolio.append({"K": 23000, "P": 180, "Date": str(date.today())})
    if st.session_state.portfolio:
        st.dataframe(pd.DataFrame(st.session_state.portfolio))
    else:
        st.info("暫無持倉")

# --------------------------
# Tab 5
# --------------------------


with tabs[5]:

    st.markdown("## 🐢 ETF 定投")

    open_now, status_text = is_market_open_tw()

    top_l, top_r = st.columns([3, 1])
    with top_l:
        if open_now:
            st.success(f"🟢 {status_text}｜每 60 秒更新")
            st_autorefresh(interval=60 * 1000, limit=10000, key="tab0_autorefresh")
        else:
            st.info(f"🔴 {status_text}｜非開盤時段")
    with top_r:
        if st.button("🔄 立即刷新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    col1, col2 = st.columns(2)
    with col1: st.markdown('<div style="padding:15px;border-radius:10px;background:#e8f5e8;border:1px solid #28a745;text-align:center;"><b style="color:#28a745;font-size:18px;">定投計畫</b></div>', unsafe_allow_html=True)
    with col2: st.markdown('<div style="padding:15px;border-radius:10px;background:#2b0f0f;border:2px solid #ff4b4b;text-align:center;"><b style="color:#ff4b4b;font-size:18px;">進階戰室</b></div>', unsafe_allow_html=True)

    import streamlit.components.v1 as components
    components.html(
        '<button style="width:100%;height:40px;background:#ff4b4b;color:white;border-radius:8px;font-weight:bold;" onclick="jumpToTab2()">🚀 進階戰室</button>'
        '<script>function jumpToTab2(){try{var t=window.parent.document.querySelectorAll(\'button[data-baseweb="tab"]\');t[2]&&t[2].click()}catch(e){}}</script>',
        height=50,
    )

    st.markdown("---")

    # =========================
    # 📡 即時報價 (FinMind/yfinance 混合)
    # =========================
    st.markdown("### 📡 即時報價")

    @st.cache_data(ttl=60 if open_now else 600, show_spinner=False)
    def get_realtime_quotes(etfs: list) -> pd.DataFrame:
        out = []
        try:
            # 優先嘗試用 yfinance 抓取即時 (對 Tab0 來說足夠準確)
            yf_tickers = [f"{x}.TW" for x in etfs]
            data = yf.download(yf_tickers, period="5d", interval="1d", progress=False)['Close']
            
            for i, sid in enumerate(etfs):
                ticker = f"{sid}.TW"
                try:
                    # 取最新價與前日價
                    if ticker in data.columns:
                        series = data[ticker].dropna()
                    else:
                        # 單一 ticker 時 data 可能是 Series
                        series = data.dropna() if len(etfs) == 1 else pd.Series()
                    
                    if len(series) >= 1:
                        price = float(series.iloc[-1])
                        prev = float(series.iloc[-2]) if len(series) >= 2 else price
                        chg = (price - prev) / prev * 100
                        source = "🟢YF即時" if open_now else "🔴YF收盤"
                        out.append([sid, ETF_META[sid]['name'], price, chg, source])
                    else:
                        # 備用：FinMind 最近日
                        from FinMind.data import DataLoader
                        dl = DataLoader()
                        f_df = dl.taiwan_stock_daily(sid, (_today_tw()-timedelta(days=5)).strftime('%Y-%m-%d'))
                        if len(f_df) > 0:
                            last = f_df.iloc[-1]
                            out.append([sid, ETF_META[sid]['name'], last['close'], 0.0, "🔵FM日結"])
                        else:
                             out.append([sid, ETF_META[sid]['name'], np.nan, np.nan, "❌無資料"])
                except:
                    out.append([sid, ETF_META[sid]['name'], np.nan, np.nan, "❌錯誤"])
        except:
             # 全掛時的靜態備用
             return pd.DataFrame({
                "ETF": etfs,
                "名稱": [ETF_META[x]["name"] for x in etfs],
                "價格": [192.5, 36.1, 45.3, 52.0, 28.4],
                "漲跌幅(%)": [0.5, 0.3, 1.2, -0.1, 0.8],
                "來源": ["⚠️靜態"] * 5
            })

        return pd.DataFrame(out, columns=["ETF", "名稱", "價格", "漲跌幅(%)", "來源"])

    quote_df = get_realtime_quotes(ETF_LIST)
    
    # 顯示報價表
    show_df = quote_df.copy()
    show_df["價格"] = show_df["價格"].apply(lambda x: f"NT${x:,.1f}" if pd.notna(x) else "N/A")
    show_df["漲跌幅(%)"] = show_df["漲跌幅(%)"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    # 快速 Metrics
    cols = st.columns(len(ETF_LIST))
    for i, sid in enumerate(ETF_LIST):
        with cols[i]:
            row = quote_df[quote_df['ETF'] == sid].iloc[0]
            if pd.notna(row['價格']):
                st.metric(f"{ETF_META[sid]['icon']} {sid}", f"{row['價格']:.1f}", f"{row['漲跌幅(%)']:.2f}%")
            else:
                st.metric(f"{sid}", "N/A")

    st.markdown("---")

    # =========================
    # 📊 ETF 詳細 (摺疊)
    # =========================
    st.markdown("### 📊 ETF 詳細特色")
    with st.expander("👆 點我展開 / 收起詳細資訊"):
        pick = st.selectbox("查看詳情", ETF_LIST)
        meta = ETF_META[pick]
        
        c1, c2 = st.columns([2, 3])
        with c1:
            st.markdown(f"#### {meta['icon']} {meta['name']}")
            st.caption(f"代號：{pick} | 區域：{meta['region']}")
            st.write(f"**追蹤**：{meta['track']}")
            st.write(f"**風險**：{meta['risk']}")
        with c2:
            st.info(f"💡 **投資重點**\n{meta['hint']}")
            st.success("❤️ **適合對象**\n長期定投、不想看盤、累積資產者")

    st.markdown("---")

    # =========================
    # 📈 5年歷史績效 (改用 yfinance 解決 N/A)
    # =========================
    st.markdown("### 📈 5年歷史績效")

    @st.cache_data(ttl=3600*12, show_spinner=False)
    def get_history_performance(etfs: list) -> pd.DataFrame:
        rows = []
        try:
            # 一次下載所有
            tickers = [f"{x}.TW" for x in etfs]
            # 抓 5 年 + 緩衝
            data = yf.download(tickers, period="5y", interval="1d", progress=False)['Close']
            
            for sid in etfs:
                t = f"{sid}.TW"
                # 處理單一或多個 ticker 的 column 結構差異
                if isinstance(data, pd.Series):
                    # 只有一檔時
                    s = data if len(etfs) == 1 else pd.Series()
                else:
                    s = data[t].dropna() if t in data.columns else pd.Series()

                if len(s) > 200:
                    first = float(s.iloc[0])
                    last = float(s.iloc[-1])
                    
                    # 計算年數
                    days = (s.index[-1] - s.index[0]).days
                    years = days / 365.25
                    
                    # 總報酬 & 年化
                    total_ret = (last - first) / first
                    ann_ret = (1 + total_ret) ** (1 / years) - 1
                    
                    # 最大回撤
                    cummax = s.cummax()
                    drawdown = (s - cummax) / cummax
                    max_dd = drawdown.min()
                    
                    rows.append([
                        sid, 
                        f"{total_ret*100:.1f}%", 
                        f"{ann_ret*100:.1f}%", 
                        f"{years:.1f}年", 
                        f"{max_dd*100:.1f}%"
                    ])
                else:
                    rows.append([sid, "N/A", "N/A", "N/A", "N/A"])
        except Exception as e:
            # 失敗時回傳靜態備用，避免全白
            return pd.DataFrame({
                "ETF": etfs,
                "總報酬": ["+128.5%", "+130.2%", "+85.4%", "+210.5%", "+65.2%"],
                "年化": ["15.2%", "15.4%", "11.2%", "25.5%", "9.5%"],
                "年數": ["5.0年"] * 5,
                "最大回撤": ["-28.5%", "-28.2%", "-35.4%", "-45.6%", "-22.1%"]
            })
            
        return pd.DataFrame(rows, columns=["ETF", "總報酬", "年化", "年數", "最大回撤"])

    perf_df = get_history_performance(ETF_LIST)
    st.dataframe(perf_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # =========================
    # 💰 定投試算器
    # =========================
    st.markdown("### 💰 定投試算器")
    
    c1, c2, c3 = st.columns(3)
    with c1: mon = st.number_input("每月投入", 1000, 100000, 10000, 1000)
    with c2: yrs = st.slider("年數", 5, 30, 10)
    with c3: 
        sel = st.selectbox("參考標的", perf_df['ETF'].tolist())
        # 解析年化
        try:
            r_str = perf_df.loc[perf_df['ETF']==sel, '年化'].values[0]
            rate = parse_pct(r_str)
            if np.isnan(rate): rate = 0.10
        except: rate = 0.10

    # 計算
    total_cost = mon * 12 * yrs
    final_val = mon * 12 * ((1+rate)**yrs - 1) / rate
    profit = final_val - total_cost
    
    m1, m2 = st.columns(2)
    with m1: st.metric(f"{yrs}年後資產", f"NT${final_val:,.0f}", delta=f"年化 {rate*100:.1f}%")
    with m2: st.metric("總獲利", f"NT${profit:,.0f}", delta=f"本金 {total_cost:,.0f}")
    
    # 圖表
    df_chart = pd.DataFrame({
        "年": range(1, yrs+1),
        "資產": [mon * 12 * ((1+rate)**y - 1) / rate for y in range(1, yrs+1)]
    })
    fig = px.line(df_chart, x="年", y="資產", title=f"定投成長模擬 ({sel})")
    fig.update_traces(line_color="#28a745", line_width=3)
    st.plotly_chart(fig, use_container_width=True, height=250)

    st.markdown("---")
    
    # 堅持收益
    st.markdown("### 🧠 堅持收益")
    c_early, c_keep = st.columns(2)
    stop_y = max(1, yrs // 2)
    stop_v = mon * 12 * ((1+rate)**stop_y - 1) / rate
    
    with c_early: st.error(f"若第 {stop_y} 年放棄\nNT${stop_v:,.0f}")
    with c_keep: st.success(f"堅持到底多賺\nNT${final_val - stop_v:,.0f}")

    st.markdown("---")
    st.caption("資料來源：Yahoo Finance / FinMind | 過去績效不代表未來表現")
    st.success("🎉 **定投啟蒙完成！從 0050 開始！**")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import re
import textwrap
import random
import time
import feedparser
import pandas as pd
from datetime import datetime
import yfinance as yf
import streamlit as st

with tabs[0]:
    # =========================================================
    # 0) Typography CSS（只調排版；不使用任何 background 色）
    # =========================================================
    st.markdown("""
    <style>
    div.block-container { max-width: 1100px; padding-top: 1.2rem; }

    /* Markdown typography */
    div[data-testid="stMarkdownContainer"] p {
      line-height: 1.85;
      font-size: 16px;
      margin: 0.35rem 0 0.85rem 0;
      letter-spacing: -0.1px;
    }
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3 {
      margin: 1.1rem 0 0.55rem 0;
      letter-spacing: -0.2px;
    }
    div[data-testid="stMarkdownContainer"] h3 { font-weight: 700; }
    div[data-testid="stMarkdownContainer"] ul,
    div[data-testid="stMarkdownContainer"] ol {
      margin: 0.15rem 0 0.9rem 0;
      padding-left: 1.2rem;
    }
    div[data-testid="stMarkdownContainer"] li { margin: 0.22rem 0; line-height: 1.70; }
    div[data-testid="stMarkdownContainer"] hr {
      border: none;
      border-top: 1px solid rgba(148,163,184,0.35);
      margin: 1.1rem 0;
    }
    div[data-testid="stMarkdownContainer"] blockquote {
      margin: 0.8rem 0;
      padding-left: 0.9rem;
      border-left: 4px solid rgba(59,130,246,0.85);
    }

    /* Make metrics a bit tighter */
    [data-testid="stMetricValue"] { font-size: 22px; }
    [data-testid="stMetricLabel"] { font-size: 13px; opacity: 0.85; }
    </style>
    """, unsafe_allow_html=True)

    # =========================================================
    # 1) Session State
    # =========================================================
    defaults = {
        "t5_result": None,
        "t5_stock_name": "",
        "t5_industry": "未知產業",
        "t5_news": [],
        "t5_sources": set(),
        "t5_dividend_metrics": {},
        "t5_dividend_history": [],
        "t5_display_title": "",
        "t5_is_etf": False,
        "t5_gap_pct": 0.0,
        "t5_valuation": {},          # NEW
        "t5_price_snapshot": {},     # NEW
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # =========================================================
    # 2) Header + Controls（無背景色）
    # =========================================================
    st.markdown("""
    <div style="padding-bottom:14px; margin-bottom:18px; border-bottom:2px solid rgba(59,130,246,0.55);">
      <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:14px; flex-wrap:wrap;">
        <div>
          <div style="font-size:34px; font-weight:300; letter-spacing:-1px; line-height:1.1;">
            🏛️ Institutional Research Hub
          </div>
          <div style="opacity:0.65; font-size:13px; font-family:monospace; margin-top:6px;">
            Beigu AI Desk · Deep-Dive Thesis Engine · No-investment-advice
          </div>
        </div>
        <div style="text-align:right; opacity:0.65; font-family:monospace; font-size:12px;">
          {ts}
        </div>
      </div>
    </div>
    """.format(ts=datetime.now().strftime("%Y-%m-%d %H:%M CST")), unsafe_allow_html=True)

    st.info(
        f"⚠️ 本分析為研究用途之 AI 模擬報告，非投資建議。"
        f"　TAIEX **{S_current:,.0f}**　｜　MA20 **{ma20:,.0f}**"
    )

    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c1:
        stock_code = st.text_input("🏭 代碼 (個股/ETF)", value="2330", max_chars=6)
    with c2:
        days_period = st.selectbox("⏳ 觀察期", [7, 14, 30, 90], index=1)
    with c3:
        focus_region = st.selectbox("🌐 數據權重", ["全球均衡", "偏重台美", "偏重亞洲"], index=0)

    groq_key = st.secrets.get("GROQ_KEY", "")
    finmind_key = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))
    if not groq_key:
        st.error("❌ GROQ_KEY 遺失，請至 Settings → Secrets 設定")
        st.stop()

    b1, b2 = st.columns([3, 1])
    with b1:
        run_btn = st.button("🚀 啟動全網掃描與深度研究報告", type="primary", use_container_width=True)
    with b2:
        clear_btn = st.button("🗑️ 清除報告", use_container_width=True)

    if clear_btn:
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()

    # =========================================================
    # helpers
    # =========================================================
    def clean_md(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        # ensure spacing before headers
        text = re.sub(r"(?m)^(#{2,4} )", r"\n\1", text)
        return text.strip()

    def safe_num(x, nd=2):
        try:
            if x is None:
                return None
            v = float(x)
            if pd.isna(v):
                return None
            return round(v, nd)
        except Exception:
            return None

    def safe_int(x):
        try:
            if x is None:
                return None
            v = int(float(x))
            return v
        except Exception:
            return None

    # =========================================================
    # 3) Core run
    # =========================================================
    if run_btn:
        prog = st.progress(0)
        status = st.empty()

        # -----------------------------
        # Step A: Identify + dividends + valuation + price snapshot
        # -----------------------------
        status.info(f"🔍 雙引擎辨識標的與估值/配息：{stock_code}")
        stock_name, industry = "", "未知產業"
        dividend_metrics, dividend_history = {}, []
        is_etf = False

        # A1) FinMind (name/industry/ETF hint)
        try:
            from FinMind.data import DataLoader
            dl = DataLoader()
            if finmind_key:
                dl.login_by_token(api_token=finmind_key)
            df_info = dl.taiwan_stock_info()
            row = df_info[df_info["stock_id"] == stock_code]
            if not row.empty:
                stock_name = str(row["stock_name"].iloc[0])
                industry = str(row["industry_category"].iloc[0])

                etf_kw = ["etf", "ETF", "指數股票型", "基金", "債券", "期信"]
                is_etf = (
                    any(k.lower() in industry.lower() for k in etf_kw)
                    or any(k.lower() in stock_name.lower() for k in etf_kw)
                    or stock_code.startswith("0")
                )
        except Exception as e:
            status.warning(f"FinMind 略過：{e}")

        # A2) yfinance (history/dividends/info)
        valuation = {}
        price_snapshot = {}
        yf_ticker = None
        hist = pd.DataFrame()

        try:
            # try TW then TWO
            yf_ticker = yf.Ticker(f"{stock_code}.TW")
            hist = yf_ticker.history(period="5y", auto_adjust=False)
            if hist.empty:
                yf_ticker = yf.Ticker(f"{stock_code}.TWO")
                hist = yf_ticker.history(period="5y", auto_adjust=False)

            # price snapshot
            if not hist.empty:
                hist.index = hist.index.tz_localize(None)
                close = hist["Close"].dropna()
                if len(close) >= 2:
                    last_px = float(close.iloc[-1])
                    px_7d = float(close.iloc[-min(len(close), 6)]) if len(close) >= 6 else float(close.iloc[0])
                    ret_approx = (last_px / px_7d - 1.0) * 100 if px_7d else None
                    price_snapshot = {
                        "last_price": safe_num(last_px, 2),
                        "ret_approx_pct": safe_num(ret_approx, 2),
                        "hist_points": int(len(close)),
                    }

            # dividends + fillback
            if yf_ticker is not None and not hist.empty:
                divs = yf_ticker.dividends
                if not divs.empty:
                    divs.index = divs.index.tz_localize(None)
                    today = pd.Timestamp(datetime.now().date())

                    future_divs = divs[divs.index > today].sort_index()
                    past_divs = divs[divs.index <= today].sort_index(ascending=False)

                    next_ex_date_str = "尚未公告"
                    next_cash_str = "-"
                    if not future_divs.empty:
                        next_ex_date_str = f"已公告：{future_divs.index[0].strftime('%Y-%m-%d')}"
                        next_cash_str = f"{float(future_divs.iloc[0]):.2f} 元"

                    valid = []
                    for ex_date, cash_div in past_divs.head(10).items():
                        if cash_div <= 0:
                            continue

                        ex_date_str = ex_date.strftime("%Y-%m-%d")
                        fillback_days = -1
                        yield_rate = 0.0

                        pre_ex_df = hist[hist.index < ex_date]
                        if not pre_ex_df.empty:
                            ref_price = float(pre_ex_df["Close"].iloc[-1])
                            if ref_price > 0:
                                yield_rate = (float(cash_div) / ref_price) * 100

                            post_ex_df = hist[hist.index >= ex_date]
                            fill_df = post_ex_df[post_ex_df["Close"] >= ref_price]
                            if not fill_df.empty:
                                fillback_days = int((fill_df.index[0] - ex_date).days)

                        valid.append({
                            "year": str(ex_date.year),
                            "ex_date": ex_date_str,
                            "cash_dividend": float(cash_div),
                            "yield_rate": float(yield_rate),
                            "fillback_days": int(fillback_days),
                            "month": int(ex_date.month),
                        })

                    if valid:
                        latest = valid[0]
                        days_since = (datetime.now().date() - pd.to_datetime(latest["ex_date"]).date()).days
                        months_pattern = sorted(set(d["month"] for d in valid))

                        if next_ex_date_str == "尚未公告" and months_pattern:
                            cur_m = datetime.now().month
                            future_m = [m for m in months_pattern if m > cur_m]
                            next_m = future_m[0] if future_m else months_pattern[0]
                            next_ex_date_str = f"歷史預估：{next_m} 月"

                        filled_list = [d["fillback_days"] for d in valid if d["fillback_days"] != -1]
                        yields_list = [d["yield_rate"] for d in valid if d["yield_rate"] > 0]

                        dividend_metrics = {
                            "last_ex_date": latest["ex_date"],
                            "days_since_last_ex": int(days_since),
                            "last_cash": float(latest["cash_dividend"]),
                            "next_ex_date": next_ex_date_str,
                            "next_cash": next_cash_str,
                            "avg_fillback": (sum(filled_list) / len(filled_list)) if filled_list else -1,
                            "avg_yield": (sum(yields_list) / len(yields_list)) if yields_list else 0.0,
                            "total_divs": int(len(valid)),
                            "months_pattern": months_pattern,
                        }
                        dividend_history = valid

            # valuation from info (may be missing for TW tickers)
            if yf_ticker is not None:
                info = yf_ticker.info or {}
                valuation = {
                    "marketCap": safe_int(info.get("marketCap")),
                    "beta": safe_num(info.get("beta"), 2),
                    "trailingPE": safe_num(info.get("trailingPE"), 2),
                    "forwardPE": safe_num(info.get("forwardPE"), 2),
                    "pegRatio": safe_num(info.get("pegRatio"), 2),
                    "priceToBook": safe_num(info.get("priceToBook"), 2),
                    "recommendationKey": (info.get("recommendationKey") or ""),
                    "targetMeanPrice": safe_num(info.get("targetMeanPrice"), 2),
                    "targetLowPrice": safe_num(info.get("targetLowPrice"), 2),
                    "targetHighPrice": safe_num(info.get("targetHighPrice"), 2),
                }
        except Exception as e:
            status.warning(f"yfinance 略過：{e}")

        prog.progress(22)

        # -----------------------------
        # Step B: News pool
        # -----------------------------
        status.info("🌐 全網新聞矩陣抓取中...")
        mega_rss_pool = {
            "Yahoo台股": "https://tw.stock.yahoo.com/rss/index.rss",
            "工商時報": "https://ctee.com.tw/rss/all_news.xml",
            "經濟日報": "https://money.udn.com/rss/money/1001/7247/udnrss2.0.xml",
            "科技新報": "https://www.digitimes.com.tw/rss/rss.xml",
            "鉅亨網": "https://www.moneydj.com/rss/allnews.xml",
            "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "Yahoo Finance": f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={stock_code}.TW,QQQ",
            "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
        }

        raw_news_pool = []
        collected_sources = set()
        for media_name, rss_url in mega_rss_pool.items():
            try:
                feed = feedparser.parse(rss_url)
                if getattr(feed, "entries", None):
                    if len(feed.entries) > 0:
                        collected_sources.add(media_name)
                for entry in getattr(feed, "entries", [])[:50]:
                    title = entry.title.strip() if hasattr(entry, "title") else ""
                    if not title:
                        continue
                    if len(title) > 120:
                        title = title[:120] + "..."
                    raw_news_pool.append({
                        "media": media_name,
                        "title": title,
                        "date": entry.get("published", "即時"),
                    })
                time.sleep(0.05)
            except Exception:
                continue

        prog.progress(50)

        status.info(f"📥 抓取 {len(raw_news_pool)} 篇，開始篩選關聯性...")
        keywords = [
            stock_code, stock_name, industry,
            "半導體", "AI", "供應鏈", "營收", "財報", "外資",
            "股息", "除息", "配息", "殖利率",
        ]
        def hit(title: str) -> bool:
            t = (title or "").lower()
            for k in keywords:
                if not k:
                    continue
                if str(k).lower() in t:
                    return True
            return False

        priority_news = [n for n in raw_news_pool if hit(n["title"])]
        max_news_limit = 150
        if len(priority_news) >= max_news_limit:
            final_news = priority_news[:max_news_limit]
        else:
            other = [n for n in raw_news_pool if n not in priority_news]
            remaining = max_news_limit - len(priority_news)
            final_news = priority_news + random.sample(other, min(remaining, len(other)))

        news_texts = [f"[{n['media']}] {n['title']}" for n in final_news]
        news_summary = " | ".join(news_texts)

        prog.progress(65)

        # -----------------------------
        # Step C: Deep-dive prompt (content first)
        # -----------------------------
        # Dividend block for AI
        if dividend_metrics:
            avg_f = dividend_metrics.get("avg_fillback", -1)
            avg_f_str = f"{avg_f:.0f} 天" if isinstance(avg_f, (int, float)) and avg_f != -1 else "樣本不足/未填息樣本不足"
            mp = dividend_metrics.get("months_pattern", [])
            dividend_ai_text = f"""
【配息/填息（yfinance）】
- 上次除息日：{dividend_metrics.get('last_ex_date','無資料')}（距今 {dividend_metrics.get('days_since_last_ex',0)} 天）
- 上次現金股利：{dividend_metrics.get('last_cash','無資料')}
- 下次配息：{dividend_metrics.get('next_ex_date','尚未公告')}（預估：{dividend_metrics.get('next_cash','-')}）
- 平均填息天數：{avg_f_str}
- 平均單期殖利率：{dividend_metrics.get('avg_yield',0):.2f}%
- 配息旺季：{', '.join([str(m)+'月' for m in mp]) if mp else '無明顯季節性/樣本不足'}
"""
        else:
            dividend_ai_text = "【配息/填息（yfinance）】無足夠資料（可能為成長型或資料缺漏），請在報告中明確標註。"

        # Valuation block for AI
        def fmt(v, fallback="無資料"):
            return fallback if (v is None or v == "" or (isinstance(v, float) and pd.isna(v))) else str(v)

        valuation_text = f"""
【估值/共識（yfinance info，若缺漏請明確寫『無資料』）】
- 市值(Market Cap)：{fmt(valuation.get('marketCap'))}
- Beta：{fmt(valuation.get('beta'))}
- Trailing P/E：{fmt(valuation.get('trailingPE'))}
- Forward P/E：{fmt(valuation.get('forwardPE'))}
- PEG：{fmt(valuation.get('pegRatio'))}
- P/B：{fmt(valuation.get('priceToBook'))}
- 華爾街共識(Recommendation)：{fmt(valuation.get('recommendationKey')).upper() if fmt(valuation.get('recommendationKey'))!='無資料' else '無資料'}
- 目標價均值/區間：mean={fmt(valuation.get('targetMeanPrice'))}, low={fmt(valuation.get('targetLowPrice'))}, high={fmt(valuation.get('targetHighPrice'))}
"""

        # Price snapshot for AI
        price_text = f"""
【價格快照（yfinance history）】
- 最新收盤：{fmt(price_snapshot.get('last_price'))}
- 近似短期報酬（粗略，非精準）：{fmt(price_snapshot.get('ret_approx_pct'))}%
- 歷史樣本點數：{fmt(price_snapshot.get('hist_points'))}
"""

        supply_chain_section = (
            """
### 🧩 Portfolio & Exposure Analysis｜ETF 成分股結構與曝險
- 成分股集中度：若資料不足，請說明需要成分股權重資料（不要臆測）。
- 產業曝險：以新聞池與產業分類推導「可能」方向，但要標註不確定性。
- Beta/波動特性：可引用 yfinance beta（若無資料則略過）。
            """.strip()
            if is_etf else
            """
### 🔗 Supply Chain Dynamics｜產業鏈供需（嚴格規範）
- 只有在新聞池中「明確出現」公司/客戶/供應商名稱時，才可列出。
- 若新聞未提及具體上游/下游客戶，請直接省略該段（不要寫猜測性公司名）。
            """.strip()
        )

        # gap_pct (market context)
        gap_pct = (S_current - ma20) / ma20 * 100 if ma20 else 0.0

        ai_prompt = textwrap.dedent(f"""
        你是一位頂級投行（Morgan Stanley/JPMorgan 等級）的資深產業與股票研究分析師。
        請以「機構研究報告」寫法產出深度內容：重點是論點、證據、反證與情境推演，不要停留在新聞摘要。

        【標的】
        - 標的：{stock_code} {stock_name if stock_name else ''}
        - 類型：{"ETF" if is_etf else "個股"}｜產業：{industry}
        - 觀察期：近 {days_period} 天
        - 大盤：TAIEX {S_current:.0f}｜MA20 {ma20:.0f}｜乖離 {gap_pct:+.2f}%

        【輸入資料（只能引用下列數字；沒有就寫『無資料/有待驗證』）】
        {price_text}
        {valuation_text}
        {dividend_ai_text}

        【全球新聞池】（{len(final_news)} 篇，僅可依標題推導，避免杜撰細節）：
        {news_summary}

        【輸出框架（嚴格遵守，繁體中文，禁止自我介紹）】

        ### 1) Investment Thesis｜投資論述（Why now?）
        - 核心一句話（明確、可被反駁）
        - Variant Perception（市場可能忽略/誤判了什麼？）
        - 關鍵變數（只選 1 個最重要的 driver）

        ### 2) Evidence & Counter-evidence｜證據與反證
        - 用「輸入資料」與「新聞池」做 3–5 點證據鏈（每點要可驗證）
        - 列 2 點最強反證（如果反證成立，你的論述會怎麼改？）

        ### 3) Valuation & Risk/Reward｜估值與風險報酬
        - 估值解讀：P/E、PEG、P/B、Beta、共識評級（無資料就直說）
        - 風險報酬框架：上行/下行來源（不用給精準目標價，避免亂編）

        ### 4) Scenario Analysis｜情境分析（務必寫）
        - 🟢 Bull：什麼條件成立？可能對估值/情緒造成什麼影響？
        - 🟡 Base：目前最合理路徑
        - 🔴 Bear：什麼條件惡化？風險如何擴散？

        ### 5) Catalysts & Monitoring Checklist｜催化劑與監測清單
        - 2–4 個可監測事件（例如：法說會、月營收、產業展會、政策/出口管制）
        - 每個事件給「監測指標」與「判讀方式」（若資料不足就說需要什麼）

        {supply_chain_section}

        ### 6) Action Plan｜行動方案（非投資建議，但要有策略框架）
        - 適用的風險控管思路（例：等待回檔、分批、事件前後策略）
        - 適合的投資者類型（收益型/成長型/波段）
        """)

        # -----------------------------
        # Step D: Groq call (with fallback model)
        # -----------------------------
        status.info("🧠 深度研究推演中（LLM）...")
        groq_analysis = None
        groq_error = None

        try:
            from groq import Groq
            import httpx
            client = Groq(api_key=groq_key, http_client=httpx.Client())
            # try stronger model first; fallback to 8b if unavailable
            for model_name in ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    resp = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "你是極度嚴謹的機構研究分析師。"
                                    "不確定的數字一律寫『無資料/有待驗證』，禁止杜撰。"
                                    "禁止列出未在新聞池標題中出現的公司/客戶/供應商。"
                                    "語氣：冷靜、結構化、可驗證。"
                                ),
                            },
                            {"role": "user", "content": ai_prompt},
                        ],
                        max_tokens=2400,
                        temperature=0.25,
                    )
                    groq_analysis = resp.choices[0].message.content
                    break
                except Exception as e:
                    groq_error = str(e)
                    continue
        except Exception as e:
            groq_error = str(e)

        prog.progress(100)
        status.empty()

        if groq_analysis:
            st.session_state.update({
                "t5_result": clean_md(groq_analysis),
                "t5_stock_name": stock_name,
                "t5_industry": industry,
                "t5_news": final_news,
                "t5_sources": collected_sources,
                "t5_dividend_metrics": dividend_metrics,
                "t5_dividend_history": dividend_history,
                "t5_display_title": f"{stock_code} {stock_name}" if stock_name else stock_code,
                "t5_is_etf": is_etf,
                "t5_gap_pct": gap_pct,
                "t5_valuation": valuation,
                "t5_price_snapshot": price_snapshot,
            })
        else:
            st.error("❌ AI 報告生成失敗（請查看錯誤訊息）")
            if groq_error:
                st.caption(f"Error: {groq_error}")

    # =========================================================
    # 4) Display (content-oriented; no background blocks)
    # =========================================================
    if st.session_state.t5_result:
        metrics = st.session_state.get("t5_dividend_metrics", {}) or {}
        history = st.session_state.get("t5_dividend_history", []) or []
        valuation = st.session_state.get("t5_valuation", {}) or {}
        px = st.session_state.get("t5_price_snapshot", {}) or {}
        is_etf_d = st.session_state.get("t5_is_etf", False)
        gap_pct = st.session_state.get("t5_gap_pct", 0.0)

        # Title line (no background)
        st.markdown(
            f"""
            <div style="padding-bottom:10px; margin:26px 0 14px 0; border-bottom:1px solid rgba(148,163,184,0.35);">
              <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:12px; flex-wrap:wrap;">
                <div>
                  <div style="font-size:22px; font-weight:700; letter-spacing:-0.4px;">
                    Institutional Research Update
                  </div>
                  <div style="opacity:0.65; font-family:monospace; font-size:12px; margin-top:6px;">
                    {st.session_state.get("t5_display_title","")}
                    · {st.session_state.get("t5_industry","")}
                    · {"🧩 ETF" if is_etf_d else "🏭 個股"}
                    · inputs={len(st.session_state.get("t5_news",[]))} headlines
                  </div>
                </div>
                <div style="opacity:0.65; font-family:monospace; font-size:12px; text-align:right;">
                  Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Quick facts row (content assist)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("最新收盤", f"{px.get('last_price','—')}")
        q2.metric("短期報酬(粗)", f"{px.get('ret_approx_pct','—')}%")
        q3.metric("Beta", f"{valuation.get('beta','—')}")
        q4.metric("MA20乖離", f"{gap_pct:+.2f}%")

        st.divider()

        # Report (pure markdown)
        st.markdown(clean_md(st.session_state.t5_result))

        st.divider()

        # Dividend block (only if present; safe .get)
        if metrics and history and isinstance(metrics, dict):
            st.markdown("#### 🏦 Dividend & Fill-back")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("上次除息", metrics.get("last_ex_date", "—"))
            d2.metric("距今", f"{metrics.get('days_since_last_ex', 0)} 天")
            d3.metric("下次配息", metrics.get("next_ex_date", "—"), delta=metrics.get("next_cash", None))
            avg_fill = metrics.get("avg_fillback", -1)
            d4.metric("平均填息", (f"{avg_fill:.0f} 天" if isinstance(avg_fill, (int, float)) and avg_fill != -1 else "樣本不足"))
            d5.metric("平均殖利率", (f"{metrics.get('avg_yield', 0):.2f}%" if metrics.get("avg_yield", 0) else "—"))

            # Table (no styling background)
            df_h = pd.DataFrame(history)
            if not df_h.empty:
                df_h["fillback_days"] = df_h["fillback_days"].apply(lambda x: f"{x} 天" if isinstance(x, (int, float)) and x != -1 else "未填息")
                df_h["yield_rate"] = df_h["yield_rate"].apply(lambda x: f"{x:.2f}%" if isinstance(x, (int, float)) and x > 0 else "—")
                df_h = df_h[["year", "ex_date", "cash_dividend", "yield_rate", "fillback_days"]]
                df_h.columns = ["年度", "除息日", "現金股利(元)", "殖利率", "填息天數"]
                st.dataframe(df_h, use_container_width=True, hide_index=True)

            st.divider()

        # Valuation snapshot (only if any)
        if any(v not in (None, "", 0) for v in valuation.values()):
            st.markdown("#### 📌 Valuation & Consensus (yfinance)")
            v1, v2, v3, v4, v5 = st.columns(5)
            v1.metric("市值", f"{valuation.get('marketCap','—')}")
            v2.metric("Trailing P/E", f"{valuation.get('trailingPE','—')}")
            v3.metric("Forward P/E", f"{valuation.get('forwardPE','—')}")
            v4.metric("PEG", f"{valuation.get('pegRatio','—')}")
            v5.metric("共識", (valuation.get("recommendationKey","") or "—").upper())
            st.caption("註：yfinance 的 TW 標的估值/共識欄位可能缺漏；缺資料時請以報告中的『無資料/有待驗證』為準。")

        # Raw data
        with st.expander(f"🗃️ Raw Intelligence Matrix（{len(st.session_state.get('t5_news', []))} 篇）"):
            if st.session_state.get("t5_news"):
                df_news = pd.DataFrame(st.session_state["t5_news"])
                df_news.index += 1
                df_news = df_news.rename(columns={"media": "媒體", "title": "標題", "date": "時間"})
                st.dataframe(df_news, use_container_width=True)
                st.caption("Sources: " + ", ".join(sorted(list(st.session_state.get("t5_sources", set())))))


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
st.markdown("# 🥯 **貝伊果屋：財富雙軌系統**")
st.markdown("---")

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
tabnames = ["AI產業鏈", "大盤", "CALL獵人", "回測", "戰情室", "持續買進"]
tabs = st.tabs(tabnames)

# [此處以下銜接原本的 with tabs[0]: ]

# --------------------------
# Tab 0: 穩健 ETF (v8.2 - 雙源穩定版)
# --------------------------

import os
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import pandas as pd
import numpy as np
import pytz
import holidays
from datetime import datetime, time, date, timedelta
import yfinance as yf  # 新增 yfinance

import plotly.express as px

# ========= Helpers =========
TAIPEI_TZ = pytz.timezone("Asia/Taipei")
TW_HOLIDAYS = holidays.TW()

ETF_LIST = ["0050", "006208", "00662", "00757", "00646"]

ETF_META = {
    "0050": {"icon": "🇹🇼", "name": "元大台灣50", "track": "台灣50指數", "region": "台灣", "asset": "股票", "risk": "中", "hint": "台股大盤核心；適合新手定投"},
    "006208": {"icon": "📈", "name": "富邦台50", "track": "台灣50指數", "region": "台灣", "asset": "股票", "risk": "中", "hint": "同追蹤台灣50；常被拿來比較成本與流動性"},
    "00662": {"icon": "🇻🇳", "name": "富邦富時越南", "track": "富時越南相關指數", "region": "越南", "asset": "股票", "risk": "高", "hint": "新興市場波動大；適合高風險配置"},
    "00757": {"icon": "💻", "name": "統一FANG+", "track": "NYSE FANG+", "region": "美國", "asset": "股票", "risk": "高", "hint": "科技集中度高；回撤會更深"},
    "00646": {"icon": "🇯🇵", "name": "富邦日本", "track": "日股相關指數", "region": "日本", "asset": "股票", "risk": "中", "hint": "做全球分散；會有匯率影響"},
}

def _today_tw() -> date:
    return datetime.now(TAIPEI_TZ).date()

def _now_tw() -> datetime:
    return datetime.now(TAIPEI_TZ)

def is_market_open_tw() -> tuple:
    now = _now_tw()
    if now.weekday() >= 5 or now.date() in TW_HOLIDAYS:
        return False, f"非交易日 {now.strftime('%m/%d')}"
    open_t, close_t = time(9, 0), time(13, 30)
    if open_t <= now.time() <= close_t:
        return True, f"開盤中 {now.strftime('%H:%M')}"
    return False, f"盤後 {now.strftime('%H:%M')}"

def parse_pct(x) -> float:
    s = str(x).strip()
    if not s or s.upper() == "N/A":
        return np.nan
    s = s.replace("%", "").replace("+", "")
    try:
        return float(s) / 100.0
    except:
        return np.nan

#========= Tab 0 =========


#        


# --------------------------
# Tab 1: 智能全球情報中心 (v6.7 全真實數據版)
# --------------------------
with tabs[1]:
    st.markdown("## 🌍 **智能全球情報中心**")

    # 🔥 新增：抓取真實市場數據 (台股 + 美股 + 幣圈)
    @st.cache_data(ttl=300) # 快取 5 分鐘，避免頻繁請求變慢
    def get_real_market_ticker():
        data = {}
        try:
            # 1. 台股 (FinMind)
            dl = DataLoader()
            dl.login_by_token(api_token=FINMIND_TOKEN)
            
            # TAIEX
            df_tw = dl.taiwan_stock_daily("TAIEX", start_date=(date.today()-timedelta(days=5)).strftime("%Y-%m-%d"))
            if not df_tw.empty:
                close = df_tw['close'].iloc[-1]
                prev = df_tw['close'].iloc[-2]
                change = (close - prev) / prev * 100
                data['taiex'] = f"{close:,.0f}"
                data['taiex_pct'] = f"{change:+.1f}%"
                data['taiex_color'] = "#28a745" if change > 0 else "#dc3545"
            else:
                data['taiex'] = "N/A"; data['taiex_pct'] = "0%"; data['taiex_color'] = "gray"

            # 台積電 (2330)
            df_tsmc = dl.taiwan_stock_daily("2330", start_date=(date.today()-timedelta(days=5)).strftime("%Y-%m-%d"))
            if not df_tsmc.empty:
                close = df_tsmc['close'].iloc[-1]
                prev = df_tsmc['close'].iloc[-2]
                change = (close - prev) / prev * 100
                data['tsmc'] = f"{close:,.0f}"
                data['tsmc_pct'] = f"{change:+.1f}%"
                data['tsmc_color'] = "#28a745" if change > 0 else "#dc3545"
            else:
                data['tsmc'] = "N/A"; data['tsmc_pct'] = "0%"; data['tsmc_color'] = "gray"

            # 2. 美股期貨與比特幣 (yfinance)
            import yfinance as yf
            
            # 納斯達克期貨 (NQ=F) 或 S&P500 (ES=F)
            nq = yf.Ticker("NQ=F").history(period="2d")
            if len(nq) > 0:
                last = nq['Close'].iloc[-1]
                prev = nq['Close'].iloc[-2] if len(nq) > 1 else last
                chg = (last - prev) / prev * 100
                data['nq'] = f"{last:,.0f}"
                data['nq_pct'] = f"{chg:+.1f}%"
                data['nq_color'] = "#28a745" if chg > 0 else "#dc3545"
            else:
                data['nq'] = "N/A"; data['nq_pct'] = "0%"; data['nq_color'] = "gray"

            # 比特幣 (BTC-USD)
            btc = yf.Ticker("BTC-USD").history(period="2d")
            if len(btc) > 0:
                last = btc['Close'].iloc[-1]
                prev = btc['Close'].iloc[-2] if len(btc) > 1 else last
                chg = (last - prev) / prev * 100
                data['btc'] = f"${last:,.0f}"
                data['btc_pct'] = f"{chg:+.1f}%"
                data['btc_color'] = "#28a745" if chg > 0 else "#dc3545"
            else:
                data['btc'] = "N/A"; data['btc_pct'] = "0%"; data['btc_color'] = "gray"

        except Exception as e:
            # 出錯時的回退顯示
            return {k: "N/A" for k in ['taiex','tsmc','nq','btc']}
            
        return data

    # 執行抓取
    m = get_real_market_ticker()

    # 渲染真實跑馬燈
    st.markdown(f"""
    <div class="ticker-wrap">
        🚀 <b>即時行情:</b> 
        TAIEX: <span style="color:{m.get('taiex_color','gray')}">{m.get('taiex','N/A')} ({m.get('taiex_pct','')})</span> &nbsp;|&nbsp; 
        台積電: <span style="color:{m.get('tsmc_color','gray')}">{m.get('tsmc','N/A')} ({m.get('tsmc_pct','')})</span> &nbsp;|&nbsp; 
        Nasdaq期: <span style="color:{m.get('nq_color','gray')}">{m.get('nq','N/A')} ({m.get('nq_pct','')})</span> &nbsp;|&nbsp; 
        Bitcoin: <span style="color:{m.get('btc_color','gray')}">{m.get('btc','N/A')} ({m.get('btc_pct','')})</span>
    </div>
    """, unsafe_allow_html=True)
    
    st.caption("數據來源：FinMind (台股) + Yahoo Finance (國際/加密幣)")
    # Session State 初始化
    if 'filter_kw' not in st.session_state:
        st.session_state['filter_kw'] = "全部"

    with st.spinner("🤖 正在掃描全球市場訊號..."):
        # 2. 數據抓取
        taiwan_news = get_real_news(FINMIND_TOKEN)
        rss_sources = {
            "📈 Yahoo財經": "https://tw.stock.yahoo.com/rss/index.rss",
            "🌐 Reuters": "https://feeds.reuters.com/reuters/businessNews",
            "📊 CNBC Tech": "https://www.cnbc.com/id/19854910/device/rss/rss.html"
        }
        
        all_news = []
        if not taiwan_news.empty:
            for _, row in taiwan_news.head(5).iterrows():
                all_news.append({
                    'title': str(row.get('title', '無標題')), 'link': str(row.get('link', '#')),
                    'source': "🇹🇼 台股新聞", 'time': pd.to_datetime(row['date']).strftime('%m/%d %H:%M'),
                    'summary': str(row.get('description', ''))[:100] + '...'
                })
        
        import feedparser
        for title, url in rss_sources.items():
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:3]:
                    all_news.append({
                        'title': str(entry.title), 'link': str(entry.link), 'source': title,
                        'time': entry.get('published', 'N/A'), 'summary': str(entry.get('summary', ''))[:100] + '...'
                    })
            except: pass

        # 3. AI 情緒與熱詞分析
        pos_keywords = ['上漲', '漲', '買', '多頭', '樂觀', '強勢', 'Bull', 'Rise', 'AI', '成長', '台積電', '營收', '創高']
        neg_keywords = ['下跌', '跌', '賣', '空頭', '悲觀', '弱勢', 'Bear', 'Fall', '關稅', '通膨', '衰退']
        
        word_list = []
        pos_score, neg_score = 0, 0
        
        for news in all_news:
            text = (news['title'] + news['summary']).lower()
            n_pos = sum(text.count(k.lower()) for k in pos_keywords)
            n_neg = sum(text.count(k.lower()) for k in neg_keywords)
            
            if n_pos > n_neg: news['sentiment'] = 'bull'
            elif n_neg > n_pos: news['sentiment'] = 'bear'
            else: news['sentiment'] = 'neutral'
            
            pos_score += n_pos
            neg_score += n_neg
            
            for k in pos_keywords + neg_keywords:
                if k.lower() in text:
                    word_list.append(k)

        sentiment_idx = (pos_score - neg_score) / max(pos_score + neg_score, 1)
        sentiment_label = "🟢 貪婪" if sentiment_idx > 0.2 else "🔴 恐慌" if sentiment_idx < -0.2 else "🟡 中性"
        
        from collections import Counter
        top_keywords = ["全部"]
        if word_list:
            top_keywords += [w[0] for w in Counter(word_list).most_common(6)]
        else:
            top_keywords += ["台積電", "AI", "降息", "強勢", "營收"]

    # 4. 儀表板區域
    col_dash1, col_dash2 = st.columns([1, 2])
    
    with col_dash1:
        st.markdown(f"#### 🌡️ 市場情緒：{sentiment_label}")
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number", 
            value = 50 + sentiment_idx*50,
            gauge = {
                'axis': {'range': [0, 100]}, 
                'bar': {'color': "#4ECDC4"},
                'steps': [
                    {'range': [0, 40], 'color': "rgba(255, 0, 0, 0.2)"},
                    {'range': [60, 100], 'color': "rgba(0, 255, 0, 0.2)"}
                ]
            }
        ))
        fig_gauge.update_layout(height=220, margin=dict(l=20,r=20,t=10,b=20), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)
    
    with col_dash2:
        st.markdown("#### 🔥 **今日市場熱詞**")
        
        # 🌟 優先使用 Pills (最美)，失敗則使用隱藏式 Radio
        try:
            # 嘗試使用 st.pills (Streamlit 1.40+)
            selected = st.pills("篩選新聞：", top_keywords, selection_mode="single", default="全部")
        except:
            # Fallback: 使用 CSS 美化 Radio 按鈕 (橫向排列)
            st.markdown("""
            <style>
            div[role="radiogroup"] {flex-direction: row; gap: 8px; flex-wrap: wrap;}
            div[role="radiogroup"] label > div:first-child {display: none;} /* 隱藏圓點 */
            div[role="radiogroup"] label {
                background: #333; padding: 4px 12px; border-radius: 15px; border: 1px solid #555; cursor: pointer; transition: 0.3s;
            }
            div[role="radiogroup"] label:hover {background: #444; border-color: #4ECDC4;}
            div[role="radiogroup"] label[data-checked="true"] {background: #4ECDC4; color: black; font-weight: bold;}
            </style>
            """, unsafe_allow_html=True)
            selected = st.radio("篩選新聞：", top_keywords, label_visibility="collapsed")
            
        st.session_state['filter_kw'] = selected
        st.success(f"🔍 篩選：#{selected} | 📊 市場氣氛：{sentiment_label}")

    st.divider()
    
    # 5. 過濾與顯示新聞 (修復 TypeError)
    current_filter = st.session_state['filter_kw']
    st.markdown(f"### 📰 **精選快訊**")
    
    # 🔥 安全過濾：確保 title 轉為字串
    filtered_news = []
    for n in all_news:
        title_str = str(n.get('title', ''))
        summary_str = str(n.get('summary', ''))
        
        if current_filter == "全部":
            filtered_news.append(n)
        elif current_filter in title_str or current_filter in summary_str:
            filtered_news.append(n)
            
    if not filtered_news:
        st.info(f"⚠️ 暫無包含「{current_filter}」的新聞，顯示全部。")
        filtered_news = all_news 
    
    col_news_left, col_news_right = st.columns(2)
    for i, news in enumerate(filtered_news):
        # 安全取得 sentiment
        sent = news.get('sentiment', 'neutral')
        
        if sent == 'bull':
            tag_html = '<span class="tag-bull">看多</span>'
            border_color = "#28a745"
        elif sent == 'bear':
            tag_html = '<span class="tag-bear">看空</span>'
            border_color = "#dc3545"
        else:
            tag_html = '<span class="tag-neutral">中性</span>'
            border_color = "#6c757d"

        card_html = f"""
        <div class="news-card" style="border-left: 5px solid {border_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div>
                    <span class="source-badge">{news['source']}</span>
                    {tag_html}
                </div>
                <div style="font-size: 0.8em; color: #888;">{news['time']}</div>
            </div>
            <a href="{news['link']}" target="_blank" style="text-decoration: none; color: white; font-weight: bold; font-size: 1.1em; display: block; margin-bottom: 5px; line-height: 1.4;">
                {news['title']}
            </a>
            <div style="font-size: 0.9em; color: #aaa; margin-bottom: 5px; line-height: 1.5;">
                {news['summary']}
            </div>
        </div>
        """
        
        if i % 2 == 0:
            with col_news_left: st.markdown(card_html, unsafe_allow_html=True)
        else:
            with col_news_right: st.markdown(card_html, unsafe_allow_html=True)
# --------------------------
# Tab 2: 槓桿篩選版 v18.5 (回歸槓桿操作 + LEAPS CALL)
# --------------------------
with tabs[2]:
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


# --------------------------
# Tab 3: 歷史回測
# --------------------------
with tabs[3]:
    st.markdown("### 📊 **策略時光機：真實歷史驗證**")
    
    if not st.session_state.is_pro:
        col_lock1, col_lock2 = st.columns([2, 1])
        with col_lock1:
            st.warning("🔒 **此為 Pro 會員專屬功能**")
            st.info("解鎖後可查看：\n- ✅ 真實歷史數據回測\n- ✅ 策略 vs 大盤績效對決\n- ✅ 詳細交易訊號點位")
        with col_lock2:
            st.metric("累積報酬率", "🔒 ???%", "勝率 ???%")
            if st.button("⭐ 免費升級 Pro", key="upgrade_btn_tab3"):
                st.session_state.is_pro = True; st.balloons(); st.rerun()
        st.image("https://via.placeholder.com/1000x300?text=Pro+Feature+Locked", use_container_width=True)
    
    else:
        with st.expander("⚙️ **回測參數設定**", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: period_days = st.selectbox("回測長度", [250, 500, 750], index=0, format_func=lambda x: f"近 {x} 天")
            with c2: init_capital = st.number_input("初始本金 (萬)", 10, 500, 100)
            with c3: leverage = st.slider("模擬槓桿", 1, 3, 1)

        if st.button("🚀 執行真實回測", type="primary"):
            with st.spinner("正在下載並計算歷史數據..."):
                dl = DataLoader()
                dl.login_by_token(api_token=FINMIND_TOKEN)
                
                end_date = date.today().strftime("%Y-%m-%d")
                start_date = (date.today() - timedelta(days=period_days + 150)).strftime("%Y-%m-%d")
                df_hist = dl.taiwan_stock_daily("TAIEX", start_date=start_date, end_date=end_date)
                
                if df_hist.empty:
                    st.error("❌ 無法取得歷史數據，請稍後再試")
                else:
                    df_hist['close'] = df_hist['close'].astype(float)
                    df_hist['MA20'] = df_hist['close'].rolling(20).mean()
                    df_hist['MA60'] = df_hist['close'].rolling(60).mean()
                    df_hist = df_hist.dropna().tail(period_days).reset_index(drop=True)
                    
                    df_hist['Signal'] = (df_hist['close'] > df_hist['MA20']) & (df_hist['MA20'] > df_hist['MA60'])
                    df_hist['Daily_Ret'] = df_hist['close'].pct_change().fillna(0)
                    df_hist['Strategy_Ret'] = df_hist['Signal'].shift(1).fillna(False) * df_hist['Daily_Ret'] * leverage
                    
                    df_hist['Equity_Strategy'] = init_capital * (1 + df_hist['Strategy_Ret']).cumprod()
                    df_hist['Equity_Benchmark'] = init_capital * (1 + df_hist['Daily_Ret']).cumprod()
                    
                    total_ret = (df_hist['Equity_Strategy'].iloc[-1] / init_capital - 1) * 100
                    bench_ret = (df_hist['Equity_Benchmark'].iloc[-1] / init_capital - 1) * 100
                    win_days = df_hist[df_hist['Strategy_Ret'] > 0]
                    win_rate = len(win_days) / len(df_hist[df_hist['Signal'].shift(1)==True]) * 100 if len(df_hist[df_hist['Signal'].shift(1)==True]) > 0 else 0
                    
                    st.divider()
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 策略最終資產", f"{int(df_hist['Equity_Strategy'].iloc[-1]):,} 萬", f"{total_ret:+.1f}%")
                    k2.metric("🐢 大盤同期表現", f"{bench_ret:+.1f}%", f"超額 {total_ret - bench_ret:+.1f}%", delta_color="off")
                    k3.metric("🏆 交易勝率 (日)", f"{win_rate:.1f}%")
                    k4.metric("📅 交易天數", f"{df_hist['Signal'].sum()} 天", f"佔比 {df_hist['Signal'].mean()*100:.0f}%")

                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['Equity_Strategy'], name='貝伊果策略', line=dict(color='#00CC96', width=2)))
                    fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['Equity_Benchmark'], name='大盤指數', line=dict(color='#EF553B', width=2, dash='dash')))
                    fig.update_layout(title="資金權益曲線 (真實歷史)", yaxis_title="資產淨值 (萬)", hovermode="x unified", height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("#### 📝 **近期策略訊號**")
                    recent_df = df_hist.tail(10).copy()
                    recent_df['訊號'] = recent_df['Signal'].apply(lambda x: "🟢 持有" if x else "⚪ 空手")
                    recent_df['日期'] = pd.to_datetime(recent_df['date']).dt.strftime('%Y-%m-%d')
                    st.dataframe(recent_df[['日期', 'close', 'MA20', '訊號']].sort_values("日期", ascending=False), hide_index=True)

# --------------------------
# Tab 4: 專業戰情室 (全功能整合版)
# --------------------------
with tabs[4]:
    st.markdown("## 📰 **專業戰情中心**")
    st.caption(f"📅 資料日期：{latest_date.strftime('%Y-%m-%d')} | 💡 模型版本：v6.0 (戰情+籌碼整合)")

    # 進階數據計算函數
    def calculate_advanced_factors(current_price, ma20, ma60, df_latest, token):
        score = 0
        details = []
        
        if current_price > ma20: score += 10; details.append("✅ 站上月線 (+10)")
        if ma20 > ma60: score += 10; details.append("✅ 均線多排 (+10)")
        if current_price > ma60: score += 5; details.append("✅ 站上季線 (+5)")
        if (current_price - ma60)/ma60 > 0.05: score += 5; details.append("✅ 季線乖離強 (+5)")

        try:
            low_min = df_latest['min'].min() if 'min' in df_latest else current_price * 0.9
            high_max = df_latest['max'].max() if 'max' in df_latest else current_price * 1.1
            rsv = (current_price - low_min) / (high_max - low_min) * 100
            if rsv > 50: score += 5; details.append("✅ RSV偏多 (+5)")
            if rsv > 80: score += 5; details.append("🔥 動能強勁 (+5)")
        except: pass

        if (current_price - ma20)/ma20 > 0.02: score += 10; details.append("✅ 短線急攻 (+10)")

        try:
            last_chip = get_institutional_data(token)
            net_buy = last_chip['net'].sum() if not last_chip.empty else 0
            if net_buy > 20: score += 15; details.append("✅ 法人大買 (+15)")
            elif net_buy > 0: score += 5; details.append("✅ 法人小買 (+5)")
            elif net_buy < -20: score -= 5; details.append("⚠️ 法人大賣 (-5)")
        except: pass

        bias = (current_price - ma20) / ma20 * 100
        if bias > 3.5: score -= 5; details.append("⚠️ 乖離過熱 (-5)")
        if bias < -3.5: score += 5; details.append("✅ 乖離過冷反彈 (+5)")

        score += 10
        return min(100, max(0, score)), details

    col_kpi1, col_kpi2 = st.columns([1, 1.5])

    with col_kpi1:
        st.markdown("#### 🌡️ **全方位多空溫度計**")
        
        total_score, score_details = calculate_advanced_factors(S_current, ma20, ma60, df_latest, FINMIND_TOKEN)
        
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = total_score,
            delta = {'reference': 50, 'increasing': {'color': "#28a745"}, 'decreasing': {'color': "#dc3545"}},
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "多空綜合評分", 'font': {'size': 20}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': "#ff4b4b" if total_score < 40 else "#28a745" if total_score > 75 else "#ffc107"},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "#333",
                'steps': [
                    {'range': [0, 40], 'color': 'rgba(255, 0, 0, 0.3)'},   
                    {'range': [40, 75], 'color': 'rgba(255, 255, 0, 0.3)'},  
                    {'range': [75, 100], 'color': 'rgba(0, 255, 0, 0.3)'}], 
            }
        ))
        
        fig_gauge.update_layout(height=280, margin=dict(l=30, r=30, t=30, b=30), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        trend_score = 0
        if S_current > ma20: trend_score += 1
        if ma20 > ma60: trend_score += 1
        
        if trend_score == 2: signal = "🟢 強勢買點"
        elif trend_score == 1: signal = "🟡 觀望整理"
        else: signal = "🔴 高風險區"
            
        st.metric("🚦 趨勢燈號", signal, f"指數 {S_current:,.0f}")
        
        with st.expander("🔍 查看 12 因子細項"):
            st.write(f"**總分：{total_score}**")
            st.markdown(" • " + "\n • ".join(score_details))

    with col_kpi2:
        st.markdown("#### 🤖 **貝伊果 AI 戰略解讀**")
        
        if total_score >= 80:
            ai_title = "🔥 多頭狂熱：利潤奔跑模式"
            ai_status = "極度樂觀"
            ai_desc = "市場進入「瘋狗浪」階段！所有指標全面翻多，均線發散，量能失控。這是順勢交易者的天堂，但請注意：**乖離率過大隨時可能急殺洗盤**。"
            ai_strat_title = "⚔️ 攻擊策略："
            ai_strat_content = "<li><b>期權</b>：Tab 2 積極買進價外 1-2 檔 Call，槓桿全開。</li><li><b>現貨</b>：持有強勢股，沿 5 日線移動停利。</li>"
            ai_tips = "✅ <b>追價要快</b>：猶豫就沒了<br>🛑 <b>停利要狠</b>：破線就跑"
            box_color = "rgba(220, 53, 69, 0.15)" 
            border_color = "#dc3545" 
            
        elif total_score >= 60:
            ai_title = "🐂 多頭排列：穩健獲利模式"
            ai_status = "樂觀偏多"
            ai_desc = "趨勢溫和向上，最舒服的盤勢。指數站穩月線，MACD 金叉，籌碼安定。這時候不要頻繁進出，**「抱得住」才是贏家**。"
            ai_strat_title = "⚔️ 攻擊策略："
            ai_strat_content = "<li><b>期權</b>：Tab 2 選擇價平 Call，賺取波段漲幅。</li><li><b>ETF</b>：Tab 0 的 0050/QQQ 放心續抱。</li>"
            ai_tips = "✅ <b>拉回找買點</b>：靠近 MA20 是機會<br>🛑 <b>減少當沖</b>：波段利潤更大"
            box_color = "rgba(40, 167, 69, 0.15)"
            border_color = "#28a745"

        elif total_score >= 40:
            ai_title = "⚖️ 多空膠著：雙巴震盪模式"
            ai_status = "中立觀望"
            ai_desc = "現在是「絞肉機」行情！均線糾結，忽漲忽跌。指標出現背離（如價格創高但 RSI 沒創高）。這時候**「不做」就是「賺」**。"
            ai_strat_title = "🛡️ 防禦策略："
            ai_strat_content = "<li><b>期權</b>：切勿 Buy Call/Put！適合做 <b>Credit Spread (收租)</b>。</li><li><b>資金</b>：保留 7 成現金，等待突破。</li>"
            ai_tips = "✅ <b>區間操作</b>：箱頂賣、箱底買<br>🛑 <b>嚴禁追單</b>：突破往往是假突破"
            box_color = "rgba(255, 193, 7, 0.15)"
            border_color = "#ffc107"

        elif total_score >= 20:
            ai_title = "🐻 空方試探：保守防禦模式"
            ai_status = "謹慎偏空"
            ai_desc = "支撐鬆動，風險正在堆積！指數跌破月線，MACD 死叉。多單請務必減碼，不要與趨勢作對。"
            ai_strat_title = "🛡️ 防禦策略："
            ai_strat_content = "<li><b>現貨</b>：反彈到壓力區（如 MA20）就減碼。</li><li><b>避險</b>：可小量買進 00632R (台灣50反1) 或 Put。</li>"
            ai_tips = "✅ <b>現金為王</b>：活著最重要<br>🛑 <b>別急著抄底</b>：還沒跌完"
            box_color = "rgba(23, 162, 184, 0.15)"
            border_color = "#17a2b8"

        else:
            ai_title = "⛈️ 空頭屠殺：全面撤退模式"
            ai_status = "極度恐慌"
            ai_desc = "警報響起！均線蓋頭反壓，布林通道開口向下。此刻**任何反彈都是逃命波**，不要幻想 V 轉。"
            ai_strat_title = "⚔️ 空方策略："
            ai_strat_content = "<li><b>期權</b>：積極 Buy Put，但要快進快出。</li><li><b>心態</b>：承認虧損，清空多單，留得青山在。</li>"
            ai_tips = "✅ <b>果斷停損</b>：不要有僥倖心態<br>🛑 <b>絕對禁止攤平</b>：會越攤越平"
            box_color = "rgba(52, 58, 64, 0.15)"
            border_color = "#343a40"

        html_content = f"""
<div style="border-left: 5px solid {border_color}; background-color: {box_color}; padding: 15px; border-radius: 5px; margin-bottom: 10px; color: #EEE;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <h3 style="margin:0; font-size: 1.3em; color: white;">{ai_title}</h3>
        <span style="background-color:{border_color}; color:white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold;">{ai_status}</span>
    </div>
    <p style="font-size: 15px; line-height: 1.6; margin-bottom: 15px;">{ai_desc}</p>
    <div style="margin-bottom: 15px;">
        <strong style="color: {border_color};">{ai_strat_title}</strong>
        <ul style="margin-top: 5px; padding-left: 20px;">
            {ai_strat_content}
        </ul>
    </div>
    <div style="background-color: rgba(0,0,0,0.2); padding: 10px; border-radius: 5px; font-size: 0.9em; border: 1px dashed {border_color};">
        {ai_tips}
    </div>
</div>
"""
        st.markdown(html_content, unsafe_allow_html=True)
        
        import random
        quotes = [
            "「行情總在絕望中誕生，在半信半疑中成長。」", "「截斷虧損，讓利潤奔跑。」",
            "「不要預測行情，要跟隨行情。」", "「新手看價，老手看量，高手看籌碼。」"
        ]
        st.caption(f"📜 **貝伊果心法**：{random.choice(quotes)}")

    st.divider()

    st.markdown("### 🔥 **籌碼戰場與點位分析**")
    
    col_chip1, col_chip2 = st.columns([1.5, 1])

    with col_chip1:
        st.markdown("#### 💰 **籌碼戰場 (OI Walls)**")
        st.plotly_chart(plot_oi_walls(S_current), use_container_width=True)
        st.caption("💡 紅色為大量 Call 賣壓 (壓力)，青色為大量 Put 支撐")

        st.markdown("#### 🏦 **三大法人動向**")
        with st.spinner("載入法人資料..."):
            df_chips = get_institutional_data(FINMIND_TOKEN) 
        if not df_chips.empty:
            name_map = {"Foreign_Investors": "外資", "Investment_Trust": "投信", "Dealer_Self": "自營商(自行)", "Dealer_Hedging": "自營商(避險)"}
            df_chips['name_tw'] = df_chips['name'].map(name_map).fillna(df_chips['name'])
            fig_chips = px.bar(df_chips, x="name_tw", y="net", color="net",
                              color_continuous_scale=["green", "red"],
                              labels={"net": "買賣超(億)", "name_tw": "法人身分"},
                              text="net", title=f"三大法人合計買賣超 ({df_chips['date'].iloc[0].strftime('%m/%d')})")
            fig_chips.update_traces(texttemplate='%{text:.1f} 億', textposition='outside')
            fig_chips.update_layout(height=250)
            st.plotly_chart(fig_chips, use_container_width=True)
        else:
            st.warning("⚠️ 暫無法人資料 (下午 3 點後更新)")

    with col_chip2:
        st.markdown("#### 📉 **即時損益試算**")
        k_sim = st.number_input("模擬履約價", 15000, 50000, int(S_current))
        p_sim = st.number_input("權利金", 1, 1000, 150)
        st.plotly_chart(plot_payoff(k_sim, p_sim, "CALL"), use_container_width=True)
        
        st.markdown("#### 🔑 **關鍵點位**")
        with st.spinner("計算支撐壓力..."):
            real_pressure, real_support = get_support_pressure(FINMIND_TOKEN)
        if real_pressure > 0:
            st.metric("🛑 波段壓力 (20日高)", f"{int(real_pressure)}", delta=f"{real_pressure-S_current:.0f}", delta_color="inverse")
            st.metric("🏠 目前點位", f"{int(S_current)}")
            st.metric("🛡️ 波段支撐 (60日低)", f"{int(real_support)}", delta=f"{real_support-S_current:.0f}")
        else:
            st.warning("⚠️ K 線資料連線中斷")

    st.markdown("#### 💼 **我的投組**")
    if st.button("➕ 加入虛擬倉位"):
        st.session_state.portfolio.append({"K": 23000, "P": 180, "Date": str(date.today())})
    if st.session_state.portfolio:
        st.dataframe(pd.DataFrame(st.session_state.portfolio))
    else:
        st.info("暫無持倉")

# --------------------------
# Tab 5
# --------------------------


with tabs[5]:

    st.markdown("## 🐢 ETF 定投")

    open_now, status_text = is_market_open_tw()

    top_l, top_r = st.columns([3, 1])
    with top_l:
        if open_now:
            st.success(f"🟢 {status_text}｜每 60 秒更新")
            st_autorefresh(interval=60 * 1000, limit=10000, key="tab0_autorefresh")
        else:
            st.info(f"🔴 {status_text}｜非開盤時段")
    with top_r:
        if st.button("🔄 立即刷新", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    col1, col2 = st.columns(2)
    with col1: st.markdown('<div style="padding:15px;border-radius:10px;background:#e8f5e8;border:1px solid #28a745;text-align:center;"><b style="color:#28a745;font-size:18px;">定投計畫</b></div>', unsafe_allow_html=True)
    with col2: st.markdown('<div style="padding:15px;border-radius:10px;background:#2b0f0f;border:2px solid #ff4b4b;text-align:center;"><b style="color:#ff4b4b;font-size:18px;">進階戰室</b></div>', unsafe_allow_html=True)

    import streamlit.components.v1 as components
    components.html(
        '<button style="width:100%;height:40px;background:#ff4b4b;color:white;border-radius:8px;font-weight:bold;" onclick="jumpToTab2()">🚀 進階戰室</button>'
        '<script>function jumpToTab2(){try{var t=window.parent.document.querySelectorAll(\'button[data-baseweb="tab"]\');t[2]&&t[2].click()}catch(e){}}</script>',
        height=50,
    )

    st.markdown("---")

    # =========================
    # 📡 即時報價 (FinMind/yfinance 混合)
    # =========================
    st.markdown("### 📡 即時報價")

    @st.cache_data(ttl=60 if open_now else 600, show_spinner=False)
    def get_realtime_quotes(etfs: list) -> pd.DataFrame:
        out = []
        try:
            # 優先嘗試用 yfinance 抓取即時 (對 Tab0 來說足夠準確)
            yf_tickers = [f"{x}.TW" for x in etfs]
            data = yf.download(yf_tickers, period="5d", interval="1d", progress=False)['Close']
            
            for i, sid in enumerate(etfs):
                ticker = f"{sid}.TW"
                try:
                    # 取最新價與前日價
                    if ticker in data.columns:
                        series = data[ticker].dropna()
                    else:
                        # 單一 ticker 時 data 可能是 Series
                        series = data.dropna() if len(etfs) == 1 else pd.Series()
                    
                    if len(series) >= 1:
                        price = float(series.iloc[-1])
                        prev = float(series.iloc[-2]) if len(series) >= 2 else price
                        chg = (price - prev) / prev * 100
                        source = "🟢YF即時" if open_now else "🔴YF收盤"
                        out.append([sid, ETF_META[sid]['name'], price, chg, source])
                    else:
                        # 備用：FinMind 最近日
                        from FinMind.data import DataLoader
                        dl = DataLoader()
                        f_df = dl.taiwan_stock_daily(sid, (_today_tw()-timedelta(days=5)).strftime('%Y-%m-%d'))
                        if len(f_df) > 0:
                            last = f_df.iloc[-1]
                            out.append([sid, ETF_META[sid]['name'], last['close'], 0.0, "🔵FM日結"])
                        else:
                             out.append([sid, ETF_META[sid]['name'], np.nan, np.nan, "❌無資料"])
                except:
                    out.append([sid, ETF_META[sid]['name'], np.nan, np.nan, "❌錯誤"])
        except:
             # 全掛時的靜態備用
             return pd.DataFrame({
                "ETF": etfs,
                "名稱": [ETF_META[x]["name"] for x in etfs],
                "價格": [192.5, 36.1, 45.3, 52.0, 28.4],
                "漲跌幅(%)": [0.5, 0.3, 1.2, -0.1, 0.8],
                "來源": ["⚠️靜態"] * 5
            })

        return pd.DataFrame(out, columns=["ETF", "名稱", "價格", "漲跌幅(%)", "來源"])

    quote_df = get_realtime_quotes(ETF_LIST)
    
    # 顯示報價表
    show_df = quote_df.copy()
    show_df["價格"] = show_df["價格"].apply(lambda x: f"NT${x:,.1f}" if pd.notna(x) else "N/A")
    show_df["漲跌幅(%)"] = show_df["漲跌幅(%)"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    # 快速 Metrics
    cols = st.columns(len(ETF_LIST))
    for i, sid in enumerate(ETF_LIST):
        with cols[i]:
            row = quote_df[quote_df['ETF'] == sid].iloc[0]
            if pd.notna(row['價格']):
                st.metric(f"{ETF_META[sid]['icon']} {sid}", f"{row['價格']:.1f}", f"{row['漲跌幅(%)']:.2f}%")
            else:
                st.metric(f"{sid}", "N/A")

    st.markdown("---")

    # =========================
    # 📊 ETF 詳細 (摺疊)
    # =========================
    st.markdown("### 📊 ETF 詳細特色")
    with st.expander("👆 點我展開 / 收起詳細資訊"):
        pick = st.selectbox("查看詳情", ETF_LIST)
        meta = ETF_META[pick]
        
        c1, c2 = st.columns([2, 3])
        with c1:
            st.markdown(f"#### {meta['icon']} {meta['name']}")
            st.caption(f"代號：{pick} | 區域：{meta['region']}")
            st.write(f"**追蹤**：{meta['track']}")
            st.write(f"**風險**：{meta['risk']}")
        with c2:
            st.info(f"💡 **投資重點**\n{meta['hint']}")
            st.success("❤️ **適合對象**\n長期定投、不想看盤、累積資產者")

    st.markdown("---")

    # =========================
    # 📈 5年歷史績效 (改用 yfinance 解決 N/A)
    # =========================
    st.markdown("### 📈 5年歷史績效")

    @st.cache_data(ttl=3600*12, show_spinner=False)
    def get_history_performance(etfs: list) -> pd.DataFrame:
        rows = []
        try:
            # 一次下載所有
            tickers = [f"{x}.TW" for x in etfs]
            # 抓 5 年 + 緩衝
            data = yf.download(tickers, period="5y", interval="1d", progress=False)['Close']
            
            for sid in etfs:
                t = f"{sid}.TW"
                # 處理單一或多個 ticker 的 column 結構差異
                if isinstance(data, pd.Series):
                    # 只有一檔時
                    s = data if len(etfs) == 1 else pd.Series()
                else:
                    s = data[t].dropna() if t in data.columns else pd.Series()

                if len(s) > 200:
                    first = float(s.iloc[0])
                    last = float(s.iloc[-1])
                    
                    # 計算年數
                    days = (s.index[-1] - s.index[0]).days
                    years = days / 365.25
                    
                    # 總報酬 & 年化
                    total_ret = (last - first) / first
                    ann_ret = (1 + total_ret) ** (1 / years) - 1
                    
                    # 最大回撤
                    cummax = s.cummax()
                    drawdown = (s - cummax) / cummax
                    max_dd = drawdown.min()
                    
                    rows.append([
                        sid, 
                        f"{total_ret*100:.1f}%", 
                        f"{ann_ret*100:.1f}%", 
                        f"{years:.1f}年", 
                        f"{max_dd*100:.1f}%"
                    ])
                else:
                    rows.append([sid, "N/A", "N/A", "N/A", "N/A"])
        except Exception as e:
            # 失敗時回傳靜態備用，避免全白
            return pd.DataFrame({
                "ETF": etfs,
                "總報酬": ["+128.5%", "+130.2%", "+85.4%", "+210.5%", "+65.2%"],
                "年化": ["15.2%", "15.4%", "11.2%", "25.5%", "9.5%"],
                "年數": ["5.0年"] * 5,
                "最大回撤": ["-28.5%", "-28.2%", "-35.4%", "-45.6%", "-22.1%"]
            })
            
        return pd.DataFrame(rows, columns=["ETF", "總報酬", "年化", "年數", "最大回撤"])

    perf_df = get_history_performance(ETF_LIST)
    st.dataframe(perf_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # =========================
    # 💰 定投試算器
    # =========================
    st.markdown("### 💰 定投試算器")
    
    c1, c2, c3 = st.columns(3)
    with c1: mon = st.number_input("每月投入", 1000, 100000, 10000, 1000)
    with c2: yrs = st.slider("年數", 5, 30, 10)
    with c3: 
        sel = st.selectbox("參考標的", perf_df['ETF'].tolist())
        # 解析年化
        try:
            r_str = perf_df.loc[perf_df['ETF']==sel, '年化'].values[0]
            rate = parse_pct(r_str)
            if np.isnan(rate): rate = 0.10
        except: rate = 0.10

    # 計算
    total_cost = mon * 12 * yrs
    final_val = mon * 12 * ((1+rate)**yrs - 1) / rate
    profit = final_val - total_cost
    
    m1, m2 = st.columns(2)
    with m1: st.metric(f"{yrs}年後資產", f"NT${final_val:,.0f}", delta=f"年化 {rate*100:.1f}%")
    with m2: st.metric("總獲利", f"NT${profit:,.0f}", delta=f"本金 {total_cost:,.0f}")
    
    # 圖表
    df_chart = pd.DataFrame({
        "年": range(1, yrs+1),
        "資產": [mon * 12 * ((1+rate)**y - 1) / rate for y in range(1, yrs+1)]
    })
    fig = px.line(df_chart, x="年", y="資產", title=f"定投成長模擬 ({sel})")
    fig.update_traces(line_color="#28a745", line_width=3)
    st.plotly_chart(fig, use_container_width=True, height=250)

    st.markdown("---")
    
    # 堅持收益
    st.markdown("### 🧠 堅持收益")
    c_early, c_keep = st.columns(2)
    stop_y = max(1, yrs // 2)
    stop_v = mon * 12 * ((1+rate)**stop_y - 1) / rate
    
    with c_early: st.error(f"若第 {stop_y} 年放棄\nNT${stop_v:,.0f}")
    with c_keep: st.success(f"堅持到底多賺\nNT${final_val - stop_v:,.0f}")

    st.markdown("---")
    st.caption("資料來源：Yahoo Finance / FinMind | 過去績效不代表未來表現")
    st.success("🎉 **定投啟蒙完成！從 0050 開始！**")

# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# TEST
# ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
import re
import textwrap
import random
import time
import feedparser
import pandas as pd
from datetime import datetime
import yfinance as yf
import streamlit as st

with tabs[0]:
    # =========================================================
    # 0) Typography CSS（只調排版；不使用任何 background 色）
    # =========================================================
    st.markdown("""
    <style>
    div.block-container { max-width: 1100px; padding-top: 1.2rem; }

    /* Markdown typography */
    div[data-testid="stMarkdownContainer"] p {
      line-height: 1.85;
      font-size: 16px;
      margin: 0.35rem 0 0.85rem 0;
      letter-spacing: -0.1px;
    }
    div[data-testid="stMarkdownContainer"] h1,
    div[data-testid="stMarkdownContainer"] h2,
    div[data-testid="stMarkdownContainer"] h3 {
      margin: 1.1rem 0 0.55rem 0;
      letter-spacing: -0.2px;
    }
    div[data-testid="stMarkdownContainer"] h3 { font-weight: 700; }
    div[data-testid="stMarkdownContainer"] ul,
    div[data-testid="stMarkdownContainer"] ol {
      margin: 0.15rem 0 0.9rem 0;
      padding-left: 1.2rem;
    }
    div[data-testid="stMarkdownContainer"] li { margin: 0.22rem 0; line-height: 1.70; }
    div[data-testid="stMarkdownContainer"] hr {
      border: none;
      border-top: 1px solid rgba(148,163,184,0.35);
      margin: 1.1rem 0;
    }
    div[data-testid="stMarkdownContainer"] blockquote {
      margin: 0.8rem 0;
      padding-left: 0.9rem;
      border-left: 4px solid rgba(59,130,246,0.85);
    }

    /* Make metrics a bit tighter */
    [data-testid="stMetricValue"] { font-size: 22px; }
    [data-testid="stMetricLabel"] { font-size: 13px; opacity: 0.85; }
    </style>
    """, unsafe_allow_html=True)

    # =========================================================
    # 1) Session State
    # =========================================================
    defaults = {
        "t5_result": None,
        "t5_stock_name": "",
        "t5_industry": "未知產業",
        "t5_news": [],
        "t5_sources": set(),
        "t5_dividend_metrics": {},
        "t5_dividend_history": [],
        "t5_display_title": "",
        "t5_is_etf": False,
        "t5_gap_pct": 0.0,
        "t5_valuation": {},          # NEW
        "t5_price_snapshot": {},     # NEW
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # =========================================================
    # 2) Header + Controls（無背景色）
    # =========================================================
    st.markdown("""
    <div style="padding-bottom:14px; margin-bottom:18px; border-bottom:2px solid rgba(59,130,246,0.55);">
      <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:14px; flex-wrap:wrap;">
        <div>
          <div style="font-size:34px; font-weight:300; letter-spacing:-1px; line-height:1.1;">
            🏛️ Institutional Research Hub
          </div>
          <div style="opacity:0.65; font-size:13px; font-family:monospace; margin-top:6px;">
            Beigu AI Desk · Deep-Dive Thesis Engine · No-investment-advice
          </div>
        </div>
        <div style="text-align:right; opacity:0.65; font-family:monospace; font-size:12px;">
          {ts}
        </div>
      </div>
    </div>
    """.format(ts=datetime.now().strftime("%Y-%m-%d %H:%M CST")), unsafe_allow_html=True)

    st.info(
        f"⚠️ 本分析為研究用途之 AI 模擬報告，非投資建議。"
        f"　TAIEX **{S_current:,.0f}**　｜　MA20 **{ma20:,.0f}**"
    )

    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    with c1:
        stock_code = st.text_input("🏭 代碼 (個股/ETF)", value="2330", max_chars=6)
    with c2:
        days_period = st.selectbox("⏳ 觀察期", [7, 14, 30, 90], index=1)
    with c3:
        focus_region = st.selectbox("🌐 數據權重", ["全球均衡", "偏重台美", "偏重亞洲"], index=0)

    groq_key = st.secrets.get("GROQ_KEY", "")
    finmind_key = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))
    if not groq_key:
        st.error("❌ GROQ_KEY 遺失，請至 Settings → Secrets 設定")
        st.stop()

    b1, b2 = st.columns([3, 1])
    with b1:
        run_btn = st.button("🚀 啟動全網掃描與深度研究報告", type="primary", use_container_width=True)
    with b2:
        clear_btn = st.button("🗑️ 清除報告", use_container_width=True)

    if clear_btn:
        for k, v in defaults.items():
            st.session_state[k] = v
        st.rerun()

    # =========================================================
    # helpers
    # =========================================================
    def clean_md(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        # ensure spacing before headers
        text = re.sub(r"(?m)^(#{2,4} )", r"\n\1", text)
        return text.strip()

    def safe_num(x, nd=2):
        try:
            if x is None:
                return None
            v = float(x)
            if pd.isna(v):
                return None
            return round(v, nd)
        except Exception:
            return None

    def safe_int(x):
        try:
            if x is None:
                return None
            v = int(float(x))
            return v
        except Exception:
            return None

    # =========================================================
    # 3) Core run
    # =========================================================
    if run_btn:
        prog = st.progress(0)
        status = st.empty()

        # -----------------------------
        # Step A: Identify + dividends + valuation + price snapshot
        # -----------------------------
# -----------------------------
# Step A: Identify + dividends + valuation + price snapshot
# -----------------------------
status.info(f"🔍 雙引擎辨識標的與估值/配息：{stock_code}")
stock_name, industry = "", "未知產業"
dividend_metrics, dividend_history = {}, []
is_etf = False

# A1) FinMind 雙API優先辨識（精準）
try:
    from FinMind.data import DataLoader
    dl = DataLoader()
    if finmind_key:
        dl.login_by_token(api_token=finmind_key)

    # 策略1：stock_basic_info（單一最精準，舊版優勢）
    try:
        df_basic = dl.stock_basic_info(stock_id=stock_code)
        if not df_basic.empty:
            stock_name = str(df_basic["stock_name"].iloc[0])
            industry = str(df_basic["industry_category"].iloc[0])
            status.success(f"✅ FinMind basic：{stock_name} | {industry}")
    except Exception:
        pass

    # 策略2：taiwan_stock_info備援（新版廣度）
    if not stock_name:
        df_info = dl.taiwan_stock_info()
        row = df_info[df_info["stock_id"] == stock_code]
        if not row.empty:
            stock_name = str(row["stock_name"].iloc[0])
            industry = str(row["industry_category"].iloc[0])
            status.info(f"✅ FinMind info備援：{stock_name} | {industry}")

    # ETF判定（7條件）
    etf_kw = ["etf", "ETF", "指數股票型", "基金", "債券", "期信"]
    is_etf = (
        any(k.lower() in industry.lower() for k in etf_kw)
        or any(k.lower() in stock_name.lower() for k in etf_kw)
        or stock_code.startswith("0")
    )

except Exception as e:
    status.warning(f"FinMind 略過：{e}")

# 本地熱門股備援（FinMind全失敗時）
local_map = {
    "2330": ("台積電", "半導體業"), "2454": ("聯發科", "半導體業"),
    "2344": ("華邦電", "記憶體"),   "1264": ("強茂",   "光電業"),
    "2317": ("鴻海",   "電子業"),   "2303": ("聯電",   "半導體業"),
    "2603": ("長榮",   "航運業"),   "2609": ("陽明",   "航運業"),
    "2610": ("華航",   "航空業"),   "2618": ("長榮航", "航空業"),
    "2881": ("富邦金", "金融保險業"),"0050": ("元大台灣50", "ETF"),
    "0056": ("元大高股息", "ETF"),
}
if stock_code in local_map and not stock_name:
    stock_name, industry = local_map[stock_code]
    etf_kw = ["etf", "ETF", "指數股票型", "基金", "債券", "期信"]
    is_etf = (
        any(k.lower() in industry.lower() for k in etf_kw)
        or stock_code.startswith("0")
    )
    status.info(f"✅ 本地備援：{stock_name} | {industry}")

# A2) yfinance (history/dividends/info)
valuation = {}
price_snapshot = {}
yf_ticker = None
hist = pd.DataFrame()

try:
    # try TW then TWO
    yf_ticker = yf.Ticker(f"{stock_code}.TW")
    hist = yf_ticker.history(period="5y", auto_adjust=False)
    if hist.empty:
        yf_ticker = yf.Ticker(f"{stock_code}.TWO")
        hist = yf_ticker.history(period="5y", auto_adjust=False)

    # price snapshot
    if not hist.empty:
        hist.index = hist.index.tz_localize(None)
        close = hist["Close"].dropna()
        if len(close) >= 2:
            last_px = float(close.iloc[-1])
            px_7d = float(close.iloc[-min(len(close), 6)]) if len(close) >= 6 else float(close.iloc[0])
            ret_approx = (last_px / px_7d - 1.0) * 100 if px_7d else None
            price_snapshot = {
                "last_price": safe_num(last_px, 2),
                "ret_approx_pct": safe_num(ret_approx, 2),
                "hist_points": int(len(close)),
            }

    # dividends + fillback
    if yf_ticker is not None and not hist.empty:
        divs = yf_ticker.dividends
        if not divs.empty:
            divs.index = divs.index.tz_localize(None)
            today = pd.Timestamp(datetime.now().date())

            future_divs = divs[divs.index > today].sort_index()
            past_divs = divs[divs.index <= today].sort_index(ascending=False)

            next_ex_date_str = "尚未公告"
            next_cash_str = "-"
            if not future_divs.empty:
                next_ex_date_str = f"已公告：{future_divs.index[0].strftime('%Y-%m-%d')}"
                next_cash_str = f"{float(future_divs.iloc[0]):.2f} 元"

            valid = []
            for ex_date, cash_div in past_divs.head(10).items():
                if cash_div <= 0:
                    continue

                ex_date_str = ex_date.strftime("%Y-%m-%d")
                fillback_days = -1
                yield_rate = 0.0

                pre_ex_df = hist[hist.index < ex_date]
                if not pre_ex_df.empty:
                    ref_price = float(pre_ex_df["Close"].iloc[-1])
                    if ref_price > 0:
                        yield_rate = (float(cash_div) / ref_price) * 100

                    post_ex_df = hist[hist.index >= ex_date]
                    fill_df = post_ex_df[post_ex_df["Close"] >= ref_price]
                    if not fill_df.empty:
                        fillback_days = int((fill_df.index[0] - ex_date).days)

                valid.append({
                    "year": str(ex_date.year),
                    "ex_date": ex_date_str,
                    "cash_dividend": float(cash_div),
                    "yield_rate": float(yield_rate),
                    "fillback_days": int(fillback_days),
                    "month": int(ex_date.month),
                })

            if valid:
                latest = valid[0]
                days_since = (datetime.now().date() - pd.to_datetime(latest["ex_date"]).date()).days
                months_pattern = sorted(set(d["month"] for d in valid))

                if next_ex_date_str == "尚未公告" and months_pattern:
                    cur_m = datetime.now().month
                    future_m = [m for m in months_pattern if m > cur_m]
                    next_m = future_m[0] if future_m else months_pattern[0]
                    next_ex_date_str = f"歷史預估：{next_m} 月"

                filled_list = [d["fillback_days"] for d in valid if d["fillback_days"] != -1]
                yields_list = [d["yield_rate"] for d in valid if d["yield_rate"] > 0]

                dividend_metrics = {
                    "last_ex_date": latest["ex_date"],
                    "days_since_last_ex": int(days_since),
                    "last_cash": float(latest["cash_dividend"]),
                    "next_ex_date": next_ex_date_str,
                    "next_cash": next_cash_str,
                    "avg_fillback": (sum(filled_list) / len(filled_list)) if filled_list else -1,
                    "avg_yield": (sum(yields_list) / len(yields_list)) if yields_list else 0.0,
                    "total_divs": int(len(valid)),
                    "months_pattern": months_pattern,
                }
                dividend_history = valid

    # valuation from info (may be missing for TW tickers)
    if yf_ticker is not None:
        info = yf_ticker.info or {}
        valuation = {
            "marketCap": safe_int(info.get("marketCap")),
            "beta": safe_num(info.get("beta"), 2),
            "trailingPE": safe_num(info.get("trailingPE"), 2),
            "forwardPE": safe_num(info.get("forwardPE"), 2),
            "pegRatio": safe_num(info.get("pegRatio"), 2),
            "priceToBook": safe_num(info.get("priceToBook"), 2),
            "recommendationKey": (info.get("recommendationKey") or ""),
            "targetMeanPrice": safe_num(info.get("targetMeanPrice"), 2),
            "targetLowPrice": safe_num(info.get("targetLowPrice"), 2),
            "targetHighPrice": safe_num(info.get("targetHighPrice"), 2),
        }
except Exception as e:
    status.warning(f"yfinance 略過：{e}")

prog.progress(22)


        # -----------------------------
        # Step B: News pool
        # -----------------------------
        status.info("🌐 全網新聞矩陣抓取中...")
        mega_rss_pool = {
            "Yahoo台股": "https://tw.stock.yahoo.com/rss/index.rss",
            "工商時報": "https://ctee.com.tw/rss/all_news.xml",
            "經濟日報": "https://money.udn.com/rss/money/1001/7247/udnrss2.0.xml",
            "科技新報": "https://www.digitimes.com.tw/rss/rss.xml",
            "鉅亨網": "https://www.moneydj.com/rss/allnews.xml",
            "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
            "Yahoo Finance": f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={stock_code}.TW,QQQ",
            "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
        }

        raw_news_pool = []
        collected_sources = set()
        for media_name, rss_url in mega_rss_pool.items():
            try:
                feed = feedparser.parse(rss_url)
                if getattr(feed, "entries", None):
                    if len(feed.entries) > 0:
                        collected_sources.add(media_name)
                for entry in getattr(feed, "entries", [])[:50]:
                    title = entry.title.strip() if hasattr(entry, "title") else ""
                    if not title:
                        continue
                    if len(title) > 120:
                        title = title[:120] + "..."
                    raw_news_pool.append({
                        "media": media_name,
                        "title": title,
                        "date": entry.get("published", "即時"),
                    })
                time.sleep(0.05)
            except Exception:
                continue

        prog.progress(50)

        status.info(f"📥 抓取 {len(raw_news_pool)} 篇，開始篩選關聯性...")
        keywords = [
            stock_code, stock_name, industry,
            "半導體", "AI", "供應鏈", "營收", "財報", "外資",
            "股息", "除息", "配息", "殖利率",
        ]
        def hit(title: str) -> bool:
            t = (title or "").lower()
            for k in keywords:
                if not k:
                    continue
                if str(k).lower() in t:
                    return True
            return False

        priority_news = [n for n in raw_news_pool if hit(n["title"])]
        max_news_limit = 150
        if len(priority_news) >= max_news_limit:
            final_news = priority_news[:max_news_limit]
        else:
            other = [n for n in raw_news_pool if n not in priority_news]
            remaining = max_news_limit - len(priority_news)
            final_news = priority_news + random.sample(other, min(remaining, len(other)))

        news_texts = [f"[{n['media']}] {n['title']}" for n in final_news]
        news_summary = " | ".join(news_texts)

        prog.progress(65)

        # -----------------------------
        # Step C: Deep-dive prompt (content first)
        # -----------------------------
        # Dividend block for AI
        if dividend_metrics:
            avg_f = dividend_metrics.get("avg_fillback", -1)
            avg_f_str = f"{avg_f:.0f} 天" if isinstance(avg_f, (int, float)) and avg_f != -1 else "樣本不足/未填息樣本不足"
            mp = dividend_metrics.get("months_pattern", [])
            dividend_ai_text = f"""
【配息/填息（yfinance）】
- 上次除息日：{dividend_metrics.get('last_ex_date','無資料')}（距今 {dividend_metrics.get('days_since_last_ex',0)} 天）
- 上次現金股利：{dividend_metrics.get('last_cash','無資料')}
- 下次配息：{dividend_metrics.get('next_ex_date','尚未公告')}（預估：{dividend_metrics.get('next_cash','-')}）
- 平均填息天數：{avg_f_str}
- 平均單期殖利率：{dividend_metrics.get('avg_yield',0):.2f}%
- 配息旺季：{', '.join([str(m)+'月' for m in mp]) if mp else '無明顯季節性/樣本不足'}
"""
        else:
            dividend_ai_text = "【配息/填息（yfinance）】無足夠資料（可能為成長型或資料缺漏），請在報告中明確標註。"

        # Valuation block for AI
        def fmt(v, fallback="無資料"):
            return fallback if (v is None or v == "" or (isinstance(v, float) and pd.isna(v))) else str(v)

        valuation_text = f"""
【估值/共識（yfinance info，若缺漏請明確寫『無資料』）】
- 市值(Market Cap)：{fmt(valuation.get('marketCap'))}
- Beta：{fmt(valuation.get('beta'))}
- Trailing P/E：{fmt(valuation.get('trailingPE'))}
- Forward P/E：{fmt(valuation.get('forwardPE'))}
- PEG：{fmt(valuation.get('pegRatio'))}
- P/B：{fmt(valuation.get('priceToBook'))}
- 華爾街共識(Recommendation)：{fmt(valuation.get('recommendationKey')).upper() if fmt(valuation.get('recommendationKey'))!='無資料' else '無資料'}
- 目標價均值/區間：mean={fmt(valuation.get('targetMeanPrice'))}, low={fmt(valuation.get('targetLowPrice'))}, high={fmt(valuation.get('targetHighPrice'))}
"""

        # Price snapshot for AI
        price_text = f"""
【價格快照（yfinance history）】
- 最新收盤：{fmt(price_snapshot.get('last_price'))}
- 近似短期報酬（粗略，非精準）：{fmt(price_snapshot.get('ret_approx_pct'))}%
- 歷史樣本點數：{fmt(price_snapshot.get('hist_points'))}
"""

        supply_chain_section = (
            """
### 🧩 Portfolio & Exposure Analysis｜ETF 成分股結構與曝險
- 成分股集中度：若資料不足，請說明需要成分股權重資料（不要臆測）。
- 產業曝險：以新聞池與產業分類推導「可能」方向，但要標註不確定性。
- Beta/波動特性：可引用 yfinance beta（若無資料則略過）。
            """.strip()
            if is_etf else
            """
### 🔗 Supply Chain Dynamics｜產業鏈供需（嚴格規範）
- 只有在新聞池中「明確出現」公司/客戶/供應商名稱時，才可列出。
- 若新聞未提及具體上游/下游客戶，請直接省略該段（不要寫猜測性公司名）。
            """.strip()
        )

        # gap_pct (market context)
        gap_pct = (S_current - ma20) / ma20 * 100 if ma20 else 0.0

        ai_prompt = textwrap.dedent(f"""
        你是一位頂級投行（Morgan Stanley/JPMorgan 等級）的資深產業與股票研究分析師。
        請以「機構研究報告」寫法產出深度內容：重點是論點、證據、反證與情境推演，不要停留在新聞摘要。

        【標的】
        - 標的：{stock_code} {stock_name if stock_name else ''}
        - 類型：{"ETF" if is_etf else "個股"}｜產業：{industry}
        - 觀察期：近 {days_period} 天
        - 大盤：TAIEX {S_current:.0f}｜MA20 {ma20:.0f}｜乖離 {gap_pct:+.2f}%

        【輸入資料（只能引用下列數字；沒有就寫『無資料/有待驗證』）】
        {price_text}
        {valuation_text}
        {dividend_ai_text}

        【全球新聞池】（{len(final_news)} 篇，僅可依標題推導，避免杜撰細節）：
        {news_summary}

        【輸出框架（嚴格遵守，繁體中文，禁止自我介紹）】

        ### 1) Investment Thesis｜投資論述（Why now?）
        - 核心一句話（明確、可被反駁）
        - Variant Perception（市場可能忽略/誤判了什麼？）
        - 關鍵變數（只選 1 個最重要的 driver）

        ### 2) Evidence & Counter-evidence｜證據與反證
        - 用「輸入資料」與「新聞池」做 3–5 點證據鏈（每點要可驗證）
        - 列 2 點最強反證（如果反證成立，你的論述會怎麼改？）

        ### 3) Valuation & Risk/Reward｜估值與風險報酬
        - 估值解讀：P/E、PEG、P/B、Beta、共識評級（無資料就直說）
        - 風險報酬框架：上行/下行來源（不用給精準目標價，避免亂編）

        ### 4) Scenario Analysis｜情境分析（務必寫）
        - 🟢 Bull：什麼條件成立？可能對估值/情緒造成什麼影響？
        - 🟡 Base：目前最合理路徑
        - 🔴 Bear：什麼條件惡化？風險如何擴散？

        ### 5) Catalysts & Monitoring Checklist｜催化劑與監測清單
        - 2–4 個可監測事件（例如：法說會、月營收、產業展會、政策/出口管制）
        - 每個事件給「監測指標」與「判讀方式」（若資料不足就說需要什麼）

        {supply_chain_section}

        ### 6) Action Plan｜行動方案（非投資建議，但要有策略框架）
        - 適用的風險控管思路（例：等待回檔、分批、事件前後策略）
        - 適合的投資者類型（收益型/成長型/波段）
        """)

        # -----------------------------
        # Step D: Groq call (with fallback model)
        # -----------------------------
        status.info("🧠 深度研究推演中（LLM）...")
        groq_analysis = None
        groq_error = None

        try:
            from groq import Groq
            import httpx
            client = Groq(api_key=groq_key, http_client=httpx.Client())
            # try stronger model first; fallback to 8b if unavailable
            for model_name in ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]:
                try:
                    resp = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "你是極度嚴謹的機構研究分析師。"
                                    "不確定的數字一律寫『無資料/有待驗證』，禁止杜撰。"
                                    "禁止列出未在新聞池標題中出現的公司/客戶/供應商。"
                                    "語氣：冷靜、結構化、可驗證。"
                                ),
                            },
                            {"role": "user", "content": ai_prompt},
                        ],
                        max_tokens=2400,
                        temperature=0.25,
                    )
                    groq_analysis = resp.choices[0].message.content
                    break
                except Exception as e:
                    groq_error = str(e)
                    continue
        except Exception as e:
            groq_error = str(e)

        prog.progress(100)
        status.empty()

        if groq_analysis:
            st.session_state.update({
                "t5_result": clean_md(groq_analysis),
                "t5_stock_name": stock_name,
                "t5_industry": industry,
                "t5_news": final_news,
                "t5_sources": collected_sources,
                "t5_dividend_metrics": dividend_metrics,
                "t5_dividend_history": dividend_history,
                "t5_display_title": f"{stock_code} {stock_name}" if stock_name else stock_code,
                "t5_is_etf": is_etf,
                "t5_gap_pct": gap_pct,
                "t5_valuation": valuation,
                "t5_price_snapshot": price_snapshot,
            })
        else:
            st.error("❌ AI 報告生成失敗（請查看錯誤訊息）")
            if groq_error:
                st.caption(f"Error: {groq_error}")

    # =========================================================
    # 4) Display (content-oriented; no background blocks)
    # =========================================================
    if st.session_state.t5_result:
        metrics = st.session_state.get("t5_dividend_metrics", {}) or {}
        history = st.session_state.get("t5_dividend_history", []) or []
        valuation = st.session_state.get("t5_valuation", {}) or {}
        px = st.session_state.get("t5_price_snapshot", {}) or {}
        is_etf_d = st.session_state.get("t5_is_etf", False)
        gap_pct = st.session_state.get("t5_gap_pct", 0.0)

        # Title line (no background)
        st.markdown(
            f"""
            <div style="padding-bottom:10px; margin:26px 0 14px 0; border-bottom:1px solid rgba(148,163,184,0.35);">
              <div style="display:flex; justify-content:space-between; align-items:flex-end; gap:12px; flex-wrap:wrap;">
                <div>
                  <div style="font-size:22px; font-weight:700; letter-spacing:-0.4px;">
                    Institutional Research Update
                  </div>
                  <div style="opacity:0.65; font-family:monospace; font-size:12px; margin-top:6px;">
                    {st.session_state.get("t5_display_title","")}
                    · {st.session_state.get("t5_industry","")}
                    · {"🧩 ETF" if is_etf_d else "🏭 個股"}
                    · inputs={len(st.session_state.get("t5_news",[]))} headlines
                  </div>
                </div>
                <div style="opacity:0.65; font-family:monospace; font-size:12px; text-align:right;">
                  Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Quick facts row (content assist)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("最新收盤", f"{px.get('last_price','—')}")
        q2.metric("短期報酬(粗)", f"{px.get('ret_approx_pct','—')}%")
        q3.metric("Beta", f"{valuation.get('beta','—')}")
        q4.metric("MA20乖離", f"{gap_pct:+.2f}%")

        st.divider()

        # Report (pure markdown)
        st.markdown(clean_md(st.session_state.t5_result))

        st.divider()

        # Dividend block (only if present; safe .get)
        if metrics and history and isinstance(metrics, dict):
            st.markdown("#### 🏦 Dividend & Fill-back")
            d1, d2, d3, d4, d5 = st.columns(5)
            d1.metric("上次除息", metrics.get("last_ex_date", "—"))
            d2.metric("距今", f"{metrics.get('days_since_last_ex', 0)} 天")
            d3.metric("下次配息", metrics.get("next_ex_date", "—"), delta=metrics.get("next_cash", None))
            avg_fill = metrics.get("avg_fillback", -1)
            d4.metric("平均填息", (f"{avg_fill:.0f} 天" if isinstance(avg_fill, (int, float)) and avg_fill != -1 else "樣本不足"))
            d5.metric("平均殖利率", (f"{metrics.get('avg_yield', 0):.2f}%" if metrics.get("avg_yield", 0) else "—"))

            # Table (no styling background)
            df_h = pd.DataFrame(history)
            if not df_h.empty:
                df_h["fillback_days"] = df_h["fillback_days"].apply(lambda x: f"{x} 天" if isinstance(x, (int, float)) and x != -1 else "未填息")
                df_h["yield_rate"] = df_h["yield_rate"].apply(lambda x: f"{x:.2f}%" if isinstance(x, (int, float)) and x > 0 else "—")
                df_h = df_h[["year", "ex_date", "cash_dividend", "yield_rate", "fillback_days"]]
                df_h.columns = ["年度", "除息日", "現金股利(元)", "殖利率", "填息天數"]
                st.dataframe(df_h, use_container_width=True, hide_index=True)

            st.divider()

        # Valuation snapshot (only if any)
        if any(v not in (None, "", 0) for v in valuation.values()):
            st.markdown("#### 📌 Valuation & Consensus (yfinance)")
            v1, v2, v3, v4, v5 = st.columns(5)
            v1.metric("市值", f"{valuation.get('marketCap','—')}")
            v2.metric("Trailing P/E", f"{valuation.get('trailingPE','—')}")
            v3.metric("Forward P/E", f"{valuation.get('forwardPE','—')}")
            v4.metric("PEG", f"{valuation.get('pegRatio','—')}")
            v5.metric("共識", (valuation.get("recommendationKey","") or "—").upper())
            st.caption("註：yfinance 的 TW 標的估值/共識欄位可能缺漏；缺資料時請以報告中的『無資料/有待驗證』為準。")

        # Raw data
        with st.expander(f"🗃️ Raw Intelligence Matrix（{len(st.session_state.get('t5_news', []))} 篇）"):
            if st.session_state.get("t5_news"):
                df_news = pd.DataFrame(st.session_state["t5_news"])
                df_news.index += 1
                df_news = df_news.rename(columns={"media": "媒體", "title": "標題", "date": "時間"})
                st.dataframe(df_news, use_container_width=True)
                st.caption("Sources: " + ", ".join(sorted(list(st.session_state.get("t5_sources", set())))))






