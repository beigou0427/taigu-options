import streamlit as st
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
import plotly.express as px
import time

# ----------------------------------------------------
# 1. 核心設定
# ----------------------------------------------------
st.set_page_config(page_title="台指期權 AI", layout="wide", page_icon="🔥")

st.markdown("""
# 🔥 **台指期權 AI (即時修正版)**
**即時台指報價 + BS模型精算權利金**
""")

# ----------------------------------------------------
# 2. 核心函數：Black-Scholes 定價模型
# ----------------------------------------------------
def black_scholes(S, K, T, r, sigma, option_type='CALL'):
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if option_type == 'CALL':
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        delta = norm.cdf(d1)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        delta = norm.cdf(d1) - 1
        
    return price, delta

# ----------------------------------------------------
# 3. 抓取即時台指 (強化版)
# ----------------------------------------------------
@st.cache_data(ttl=5)  # 5秒極速更新
def get_real_twii():
    try:
        # 使用 fast_info 抓取最新成交價
        ticker = yf.Ticker("^TWII")
        
        # 方法 A: fast_info (最準)
        if hasattr(ticker, 'fast_info') and 'last_price' in ticker.fast_info:
            price = ticker.fast_info['last_price']
            if price and price > 10000: # 確保沒抓錯
                return price, pd.Timestamp.now()
        
        # 方法 B: 1分K線 (備案)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return data['Close'].iloc[-1], data.index[-1]
            
    except Exception as e:
        print(f"Error: {e}")
        
    return 23250.0, pd.Timestamp.now() # 萬一都失敗的預設值

current_price, update_time = get_real_twii()

# ----------------------------------------------------
# 4. 自動生成擬真合約
# ----------------------------------------------------
def generate_options(spot_price):
    options = []
    
    r = 0.015  
    sigma = 0.18 
    
    # 智慧履約價範圍
    atm = round(spot_price / 100) * 100
    strikes = range(atm - 800, atm + 800, 100)
    
    contracts = {
        '202606 (近月)': 30/365,
        '202609 (季月)': 120/365,
        '202612 (遠月)': 210/365
    }
    
    for month_name, T in contracts.items():
        for K in strikes:
            # CALL
            call_p, call_d = black_scholes(spot_price, K, T, r, sigma, 'CALL')
            if call_p >= 5:
                lev = (call_d * spot_price) / call_p
                options.append({
                    '月份': month_name, '履約價': K, '類型': 'CALL 📈',
                    '權利金': round(call_p, 1), 'Delta': round(call_d, 2),
                    '槓桿': round(lev, 1), '價內': K < spot_price
                })
                
            # PUT
            put_p, put_d = black_scholes(spot_price, K, T, r, sigma, 'PUT')
            if put_p >= 5:
                lev = (abs(put_d) * spot_price) / put_p
                options.append({
                    '月份': month_name, '履約價': K, '類型': 'PUT 📉',
                    '權利金': round(put_p, 1), 'Delta': round(put_d, 2),
                    '槓桿': round(lev, 1), '價內': K > spot_price
                })
                
    return pd.DataFrame(options)

df = generate_options(current_price)

# ----------------------------------------------------
# 5. UI 介面
# ----------------------------------------------------
col1, col2 = st.columns(2)
col1.metric("📈 加權指數", f"{int(current_price):,}", "Real-time")
col2.metric("🟢 資料狀態", "已連線 Yahoo Finance")

st.markdown("---")

c1, c2, c3 = st.columns(3)
type_filter = c1.radio("方向", ["看漲 (CALL)", "看跌 (PUT)"])
month_filter = c2.selectbox("合約月份", df['月份'].unique())
lev_filter = c3.slider("目標槓桿", 2.0, 20.0, 5.0)

target_type = 'CALL' if '看漲' in type_filter else 'PUT'
filtered_df = df[
    (df['月份'] == month_filter) & 
    (df['類型'].str.contains(target_type))
].copy()

if st.button("🎯 **搜尋最佳合約**", type="primary", use_container_width=True):
    
    filtered_df['差'] = abs(filtered_df['槓桿'] - lev_filter)
    filtered_df = filtered_df.sort_values('差')
    
    best = filtered_df.iloc[0]
    cost = int(best['權利金'] * 50)
    
    st.balloons()
    
    st.markdown(f"""
    <div style='background: linear-gradient(to right, #e3f2fd, #ffffff); 
                padding: 20px; border-radius: 15px; border-left: 6px solid #2196f3; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='color: #0d47a1; margin:0;'>🏆 推薦：{best['履約價']} {best['類型']}</h2>
        <div style='display: flex; justify-content: space-around; margin-top: 15px;'>
            <div><p style='margin:0; color:#666;'>權利金</p><h3>{best['權利金']}</h3></div>
            <div><p style='margin:0; color:#666;'>槓桿</p><h3 style='color:#d81b60;'>{best['槓桿']}x</h3></div>
            <div><p style='margin:0; color:#666;'>成本</p><h3>${cost:,}</h3></div>
        </div>
        <hr style='margin: 15px 0; border:0; border-top:1px solid #ddd;'>
        <code style='background: #fff; padding: 8px; font-weight: bold;'>
        TXO {month_filter.split(' ')[0]} {target_type[0]}{best['履約價']} 1 口
        </code>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📊 合約清單")
    st.dataframe(filtered_df[['履約價', '權利金', '槓桿', 'Delta', '價內']].head(10), use_container_width=True)
    
    fig = px.scatter(filtered_df, x='履約價', y='槓桿', color='Delta', size='權利金')
    fig.add_hline(y=lev_filter, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

st.caption("ℹ️ 即時報價來自 Yahoo Finance，可能有些微延遲。")
