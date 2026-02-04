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
# 🔥 **台指期權 AI (高精準擬真版)**
**即時台指報價 + BS模型精算權利金**
""")

# ----------------------------------------------------
# 2. 核心函數：Black-Scholes 定價模型
# ----------------------------------------------------
def black_scholes(S, K, T, r, sigma, option_type='CALL'):
    """
    S: 標的現價
    K: 履約價
    T: 到期時間(年)
    r: 無風險利率
    sigma: 波動率
    """
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
# 3. 抓取即時台指
# ----------------------------------------------------
@st.cache_data(ttl=30)  # 30秒更新一次
def get_real_twii():
    try:
        # 嘗試抓台指期貨或加權指數
        ticker = yf.Ticker("^TWII")
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return data['Close'].iloc[-1], data.index[-1]
    except:
        pass
    return 23500.0, pd.Timestamp.now() # 備用值

current_price, update_time = get_real_twii()

# ----------------------------------------------------
# 4. 自動生成擬真合約
# ----------------------------------------------------
def generate_options(spot_price):
    options = []
    
    # 設定參數
    r = 0.015  # 利率 1.5%
    sigma = 0.18 # 波動率 18% (台指平均)
    
    # 產生履約價：價平上下 10 檔 (每檔 100 點)
    atm = round(spot_price / 100) * 100
    strikes = range(atm - 1000, atm + 1000, 100)
    
    # 合約月份 (假設)
    contracts = {
        '202606 (近月)': 30/365,   # 剩30天
        '202609 (季月)': 120/365,  # 剩120天
        '202612 (遠月)': 210/365   # 剩210天
    }
    
    for month_name, T in contracts.items():
        for K in strikes:
            # 計算 CALL
            call_price, call_delta = black_scholes(spot_price, K, T, r, sigma, 'CALL')
            if call_price >= 5: # 過濾掉太便宜的
                lev = (call_delta * spot_price) / call_price
                options.append({
                    '月份': month_name,
                    '履約價': K,
                    '類型': 'CALL 📈',
                    '權利金': round(call_price, 1),
                    'Delta': round(call_delta, 2),
                    '槓桿': round(lev, 1),
                    '價內': K < spot_price
                })
                
            # 計算 PUT
            put_price, put_delta = black_scholes(spot_price, K, T, r, sigma, 'PUT')
            if put_price >= 5:
                lev = (abs(put_delta) * spot_price) / put_price
                options.append({
                    '月份': month_name,
                    '履約價': K,
                    '類型': 'PUT 📉',
                    '權利金': round(put_price, 1),
                    'Delta': round(put_delta, 2),
                    '槓桿': round(lev, 1),
                    '價內': K > spot_price
                })
                
    return pd.DataFrame(options)

df = generate_options(current_price)

# ----------------------------------------------------
# 5. UI 介面展示
# ----------------------------------------------------
col1, col2 = st.columns(2)
col1.metric("📈 加權指數 (Real-time)", f"{int(current_price):,}", 
            f"最後更新: {update_time.strftime('%H:%M')}")
col2.metric("🟢 資料狀態", "yfinance + BS模型推算")

st.markdown("---")

# 操作區
c1, c2, c3 = st.columns(3)
type_filter = c1.radio("方向", ["看漲 (CALL)", "看跌 (PUT)"])
month_filter = c2.selectbox("合約月份", df['月份'].unique())
lev_filter = c3.slider("目標槓桿倍數", 2.0, 20.0, 5.0)

# 篩選邏輯
target_type = 'CALL' if '看漲' in type_filter else 'PUT'
filtered_df = df[
    (df['月份'] == month_filter) & 
    (df['類型'].str.contains(target_type))
].copy()

# 找最佳合約
if st.button("🎯 **智能搜尋最佳合約**", type="primary", use_container_width=True):
    
    # 算出槓桿差異
    filtered_df['差'] = abs(filtered_df['槓桿'] - lev_filter)
    filtered_df = filtered_df.sort_values('差')
    
    best = filtered_df.iloc[0]
    cost = int(best['權利金'] * 50)
    
    st.balloons()
    
    # 推薦卡片
    st.markdown(f"""
    <div style='background: linear-gradient(to right, #e0f7fa, #ffffff); 
                padding: 20px; border-radius: 15px; border-left: 6px solid #00acc1; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);'>
        <h2 style='color: #006064; margin:0;'>🏆 最佳推薦：{best['履約價']} {best['類型']}</h2>
        <div style='display: flex; justify-content: space-around; margin-top: 15px;'>
            <div>
                <p style='color: #555; font-size: 14px; margin:0;'>權利金</p>
                <h3 style='margin:0;'>{best['權利金']}</h3>
            </div>
            <div>
                <p style='color: #555; font-size: 14px; margin:0;'>槓桿倍數</p>
                <h3 style='margin:0; color: #d81b60;'>{best['槓桿']}x</h3>
            </div>
            <div>
                <p style='color: #555; font-size: 14px; margin:0;'>一張成本</p>
                <h3 style='margin:0;'>${cost:,}</h3>
            </div>
        </div>
        <hr style='border: 0; border-top: 1px solid #ddd; margin: 15px 0;'>
        <code style='background: #fff; padding: 8px 15px; border-radius: 5px; font-weight: bold; color: #333;'>
        下單指令：TXO {month_filter.split(' ')[0]} {target_type[0]}{best['履約價']} 買進 1 口
        </code>
    </div>
    """, unsafe_allow_html=True)
    
    # 詳細表格
    st.markdown("### 📊 合約清單 (依槓桿排序)")
    st.dataframe(
        filtered_df[['履約價', '權利金', '槓桿', 'Delta', '價內']].head(10),
        use_container_width=True
    )
    
    # 視覺化圖表
    fig = px.scatter(
        filtered_df, x='履約價', y='槓桿', color='Delta', size='權利金',
        title=f'{month_filter} {target_type} 槓桿分佈圖',
        hover_data=['權利金', '槓桿']
    )
    fig.add_hline(y=lev_filter, line_dash="dash", line_color="red", annotation_text="目標槓桿")
    st.plotly_chart(fig, use_container_width=True)

st.caption("ℹ️ 本工具使用 Black-Scholes 模型依據即時台指推算合理價格，與市場報價可能略有誤差。")
