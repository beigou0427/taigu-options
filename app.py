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
# ==========================
with tabs[0]:
    # State
    keys = ['results_lev_v188','best_lev_v188','backtest_lev_v188']
    for k in keys: 
        if k not in st.session_state: st.session_state[k] = None if 'best' in k else []
    
    st.markdown("### ♟️ **LEAPS槓桿戰情室**")
    col_left, col_right = st.columns([1.3, 0.7])

    # Functions
    def calc_score(delta,days,vol,S,K,optype):
        sd=abs(delta)*100; m=(S-K)/S if optype=="CALL" else (K-S)/S
        sm=max(-10,min(m*200,10))+50; st=min(days/90*100,100); sv=min(vol/5000*100,100)
        return 0.4*sd+0.2*sm+0.2*st+0.2*sv

    def micro_winrate(res):
        if not res: return []
        res=sorted(res,key=lambda x:x['raw_score'],reverse=True)
        n,topn=len(res),max(1,int(0.4*n))
        for i in range(n):
            if i<topn: score=95-(i/(topn-1))*5 if topn>1 else 95
            else: rem,idx=n-topn,i-topn; score=85-(idx/(rem-1))*70 if rem>1 else 15
            res[i]['勝率']=round(score,1)
        return res

    # ✅ 內嵌台指數據
    @st.cache_data
    def get_mock_taiex(): 
        dates=pd.date_range('2025-06-01',periods=60,freq='B')
        prices=23000+np.cumsum(np.random.normal(0,120,60))
        df=pd.DataFrame({'close':prices},index=dates)
        df['ret']=df['close'].pct_change().fillna(0)
        return df

    df_taiex = get_mock_taiex()

    def lev_backtest(df,con):
        d,a=abs(con['Delta']),con['槓桿']
        rets=[]
        for i in range(1,min(20,len(df))):
            mr=df['ret'].iloc[-i]
            lr=mr*d*a-0.0005
            rets.append(lr*100)
        if not rets: return dict(win_rate=0,avg_return=0,sharpe=0,trades=0,lev=a)
        wr=sum(r>0 for r in rets)/len(rets)*100
        ar,vl=np.mean(rets),np.std(rets)
        sh=ar/vl if vl>0.001 else 0
        return dict(win_rate=round(wr,1),avg_return=round(ar,2),sharpe=round(sh,2),trades=len(rets),lev=round(a,1))

    # 掃描面板
    with col_left:
        st.markdown("#### 🔍 **掃描**")
        if df_latest.empty: st.error("無資料");st.stop()
        
        dfw=df_latest.copy()
        for c in ['close','volume','strike_price']:dfw[c]=pd.to_numeric(dfw[c],errors='coerce').fillna(0)
        dfw['call_put']=dfw['call_put'].str.upper().str.strip()

        c1,c2,c3,c4=st.columns([1,1,1,0.6])
        with c1: 
            mode=st.selectbox("方向",["📈CALL","📉PUT"],key="d_v188")
            tp="CALL" if "CALL" in mode else "PUT"
        with c2:
            cons=dfw[dfw.call_put==tp].contract_date.dropna()
            av=sorted(cons[cons.astype(str).str.len()==6].unique())
            sc=st.selectbox("月份",av if av else [""],index=len(av)-1 if av else 0,key="c_v188")
        with c3: 
            tl=st.slider("槓桿",2.0,20.0,5.0,0.5,key="l_v188")  # ✅ 浮點修復
        with c4: 
            if st.button("🧹",key="r_v188"):
                for k in keys: st.session_state[k]=None if 'best' in k else []
                st.rerun()

        if st.button("🚀",type="primary",key="s_v188"):
            st.session_state['results_lev_v188']=st.session_state['best_lev_v188']=st.session_state['backtest_lev_v188']=None
            if sc and len(str(sc))==6:
                tdf=dfw[(dfw.contract_date.astype(str)==sc)&(dfw.call_put==tp)]
                if not tdf.empty:
                    y,m=int(str(sc)[:4]),int(str(sc)[4:])
                    days=max((date(y,m,15)-latest_date.date()).days,1)
                    T,T1=days/365,0.02+0.5*0.04
                    
                    rslts=[]
                    for _,rw in tdf.iterrows():
                        K,V,C=float(rw.strike_price),float(rw.volume),float(rw.close)
                        if K<=0 or C<=0.5:continue
                        try:
                            d1=(np.log(S_current/K)+T1*T)/(0.2*np.sqrt(T))
                            dl=norm.cdf(d1) if tp=="CALL" else -norm.cdf(-d1)
                        except:dl=0.5
                        if abs(dl)<0.1:continue
                        P=C if V>0 else C
                        lv=abs(dl)*S_current/P
                        sc=calc_score(dl,days,V,S_current,K,tp)
                        rslts.append(dict(履約價=int(K),價格=P,槓桿=lv,Delta=dl,raw_score=sc,
                                        差距=abs(lv-tl),合約=sc,類型=tp,天數=days))
                    
                    if rslts:
                        fnl=micro_winrate(rslts)
                        fnl.sort(key=lambda x:(x['差距'],-x['勝率'],-x['天數']))
                        st.session_state['results_lev_v188']=fnl[:15]
                        st.session_state['best_lev_v188']=fnl[0]
                        st.success(f"✅ {fnl[0]['槓桿']:.1f}x")
            st.rerun()

        if st.session_state['results_lev_v188']:
            bst=st.session_state['best_lev_v188']
            st.markdown("---")
            ca,cb=st.columns([2,1])
            with ca:
                st.markdown("#### 🏆 **推薦**")
                st.markdown(f"`{bst['合約']}{bst['履約價']}C` **{int(bst['價格'])}**")
                st.caption(f"{bst['槓桿']:.1f}x | {bst['勝率']}%")
            with cb:
                if st.button("📊回測",key="bt_v188"):
                    bt=lev_backtest(df_taiex,bst)
                    st.session_state['backtest_lev_v188']=bt
                    st.rerun()

            with st.expander("結果"):
                dfp=pd.DataFrame(st.session_state['results_lev_v188'])
                dfp['權利金']=dfp['價格'].round().astype(int)
                dfp['槓桿']=dfp['槓桿'].map(lambda x:f"{x:.1f}x")
                st.dataframe(dfp[['合約','履約價','權利金','槓桿','勝率']],hide_index=True)

    # 回測面板
    with col_right:
        st.markdown("#### 📈 **回測**")
        if st.session_state['backtest_lev_v188']:
            bt=st.session_state['backtest_lev_v188']
            c1,c2,c3=st.columns(3)
            with c1:st.metric("勝率",f"{bt['win_rate']}%")
            with c2:st.metric("報酬",f"{bt['avg_return']}%")
            with c3:st.metric("夏普",f"{bt['sharpe']:.1f}")
            st.caption(f"{bt['trades']}日 {bt['lev']}x")
            if st.button("X",key="clbt_v188"):st.session_state['backtest_lev_v188']=None;st.rerun()
        else:st.info("點回測")

    st.markdown("---")
    st.markdown("**台指×槓桿模擬** | 內嵌數據 | 夏普>0.5為佳")






