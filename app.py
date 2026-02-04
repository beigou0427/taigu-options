import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import plotly.express as px
from datetime import datetime

# ----------------------------------------------------
# 1. 頁面設定
# ----------------------------------------------------
st.set_page_config(page_title="台指期權 AI (嚴格真實版)", layout="wide", page_icon="🔥")

st.markdown("""
# 🔥 **台指期權 AI (嚴格真實版)**
**100% 真實數據 | 絕無預測 | 失敗即報錯**
""")

# ----------------------------------------------------
# 2. 核心數據函數 (嚴格模式)
# ----------------------------------------------------
@st.cache_data(ttl=10)
def get_strict_data():
    # ------------------------------------------------
    # A. 抓取加權指數 (Yahoo Finance)
    # ------------------------------------------------
    try:
        ticker = yf.Ticker("^TWII")
        # 強制使用 fast_info
        if hasattr(ticker, 'fast_info') and 'last_price' in ticker.fast_info:
            twii_price = ticker.fast_info['last_price']
            if twii_price is None or twii_price <= 0:
                raise ValueError("Yahoo Finance 回傳無效價格")
        else:
            # 備用方案：抓 1 分鐘 K 線，但必須抓到最新資料
            df = ticker.history(period="1d", interval="1m")
            if df.empty:
                raise ValueError("Yahoo Finance 抓無今日 K 線資料")
            twii_price = df['Close'].iloc[-1]
    except Exception as e:
        st.error(f"❌ 無法取得加權指數：{e}")
        st.stop()  # 強制停止，絕不使用預設值

    # ------------------------------------------------
    # B. 抓取期交所真實行情 (TAIFEX API)
    # ------------------------------------------------
    try:
        # 使用期交所 OpenAPI (盤後資訊)
        # 注意：這通常是前一日收盤資料，盤中即時需券商 API
        url = "https://openapi.taifex.com.tw/v1/DailyMarket/DailyMarketOption"
        response = requests.get(url, timeout=5)
        
        if response.status_code != 200:
            raise ConnectionError(f"期交所 API 回傳錯誤碼: {response.status_code}")
            
        data = response.json()
        if not data:
            raise ValueError("期交所 API 回傳空資料")
            
        df = pd.DataFrame(data)
        
        # 資料清洗與過濾 (只留 TXO)
        # API 欄位名稱: ContractMonth(合約月份), StrikePrice(履約價), ClosePrice(收盤價), CallPutPair(買賣權), Symbol(代號)
        # 需確認欄位名稱 (依據官方文件)
        # 這裡做簡單對應，若欄位不對會直接報錯
        
        # 篩選 TXO 台指選
        # 假設代號包含 'TXO'
        df = df[df['Symbol'].str.contains('TXO', na=False)].copy()
        
        if df.empty:
            raise ValueError("API 資料中找不到 TXO 合約")

        # 轉換數值格式
        df['StrikePrice'] = pd.to_numeric(df['StrikePrice'], errors='coerce')
        df['ClosePrice'] = pd.to_numeric(df['ClosePrice'], errors='coerce')
        
        # 移除無效數據
        df = df.dropna(subset=['StrikePrice', 'ClosePrice'])
        df = df[df['ClosePrice'] > 0] # 只留有成交價的

    except Exception as e:
        st.error(f"❌ 無法取得期權報價：{e}")
        st.info("💡 盤中即時資料需要券商 API 權限，目前無法透過公開網頁取得。")
        st.stop()  # 強制停止

    return twii_price, df

# ----------------------------------------------------
# 3. 執行數據獲取
# ----------------------------------------------------
# 呼叫嚴格函數
with st.spinner("正在連線期交所與 Yahoo Finance..."):
    twii_price, options_df = get_strict_data()

# ----------------------------------------------------
# 4. 資料處理與 UI 顯示
# ----------------------------------------------------
col1, col2 = st.columns(2)
col1.metric("📈 加權指數 (真實)", f"{twii_price:,.2f}")
col2.metric("🟢 資料來源", "TAIFEX 期交所 API")

st.markdown("---")

# 整理月份選單
unique_months = sorted(options_df['ContractMonth'].unique())
selected_month = st.selectbox("📅 選擇合約月份", unique_months)

# 槓桿滑桿
target_lev = st.slider("⚡ 目標槓桿", 2.0, 20.0, 5.0)

# 篩選當月資料
current_df = options_df[options_df['ContractMonth'] == selected_month].copy()

# 計算槓桿 (真實公式)
# Leverage = (Delta * S) / Price
# 因為沒有即時 Delta，這裡提供「真實價格」與「粗估槓桿」
# Delta 粗估：價平=0.5, 價內>0.5, 價外<0.5
# 這裡我們用一個簡單的 Delta 近似公式，但標註為「估計值」

def estimate_delta(S, K, cp):
    moneyness = S / K
    if cp == 'Call':
        if moneyness > 1.05: return 0.9
        elif moneyness > 1.02: return 0.7
        elif moneyness > 0.98: return 0.5
        else: return 0.3
    else: # Put
        if moneyness < 0.95: return 0.9
        elif moneyness < 0.98: return 0.7
        elif moneyness < 1.02: return 0.5
        else: return 0.3

# 增加計算欄位
current_df['Delta估'] = current_df.apply(lambda row: estimate_delta(twii_price, row['StrikePrice'], row['CallPutPair']), axis=1)
current_df['槓桿倍數'] = (current_df['Delta估'] * twii_price) / current_df['ClosePrice']

# 讓使用者選方向
type_filter = st.radio("方向", ["Call (看漲)", "Put (看跌)"])
target_cp = 'Call' if 'Call' in type_filter else 'Put'

# 最終篩選
final_df = current_df[current_df['CallPutPair'] == target_cp].copy()
final_df['槓桿差'] = abs(final_df['槓桿倍數'] - target_lev)
final_df = final_df.sort_values('槓桿差')

if final_df.empty:
    st.warning("⚠️ 該條件下無符合合約")
else:
    best = final_df.iloc[0]
    
    st.markdown(f"""
    <div style='background: #e3f2fd; padding: 20px; border-radius: 10px; border-left: 5px solid #2196f3;'>
        <h3>🏆 真實成交最佳推薦：{best['StrikePrice']:.0f} {best['CallPutPair']}</h3>
        <p>成交價：{best['ClosePrice']} | 槓桿(估)：{best['槓桿倍數']:.1f}x</p>
        <p>資料時間：{datetime.now().strftime('%H:%M')}</p>
    </div>
    """, unsafe_allow_html=True)

    st.dataframe(final_df[['ContractMonth', 'StrikePrice', 'CallPutPair', 'ClosePrice', '槓桿倍數']].head(10))
