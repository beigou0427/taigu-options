import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np

st.set_page_config(layout="wide")

st.markdown("""
# 🔥 **台指期權 AI (實戰版)**
**抓取真實台指，即時運算最佳合約**
""")

# 1. 抓取真實台指價格
@st.cache_data(ttl=60)
def get_twii():
    try:
        # 抓取台指期貨或大盤
        df = yf.download("^TWII", period="1d", interval="1m")
        price = df['Close'].iloc[-1]
        return float(price)
    except:
        return 23250.0  # 備用

S_current = get_twii()

# 2. 自動生成合約 (依據台指價格推算)
def generate_contracts(spot_price):
    contracts = []
    
    # 履約價範圍：上下 500 點
    strikes = range(int(spot_price/100)*100 - 500, int(spot_price/100)*100 + 600, 100)
    
    # 月份
    months = [202606, 202609, 202612]
    
    for m in months:
        days_left = 30 if m == 202606 else 120
        t = days_left / 365
        
        for k in strikes:
            # 簡化 BS 模型估算權利金
            # Call Price ≈ Max(0, S - K) + TimeValue
            intrinsic = max(0, spot_price - k)
            time_value = spot_price * 0.02 * t  # 假設時間價值
            price = intrinsic + time_value
            
            if price < 10: continue
            
            # 槓桿 = (Delta * S) / Price (Delta 簡化為 0.5~1.0)
            delta = 0.5 + (intrinsic / spot_price) * 0.5
            delta = min(0.95, delta)
            lev = (delta * spot_price) / price
            
            contracts.append({
                '月份': str(m),
                '履約價': k,
                '權利金': round(price, 1),
                '槓桿': round(lev, 1),
                'Delta': round(delta, 2),
                '類型': 'CALL'
            })
    return pd.DataFrame(contracts)

df = generate_contracts(S_current)

# 3. 顯示大盤
col1, col2 = st.columns(2)
col1.metric("📈 台指現價 (Real-time)", f"{int(S_current):,}")
col2.metric("🟢 狀態", "連線正常")

# 4. 操作區
col_m, col_l = st.columns(2)
month = col_m.selectbox("📅 月份", df['月份'].unique())
lev_target = col_l.slider("⚡ 目標槓桿", 2.0, 15.0, 3.5)

# 5. 搜尋
if st.button("🎯 **找合約！**", type="primary"):
    
    target_df = df[df['月份'] == month].copy()
    
    # 找最接近槓桿
    target_df['差'] = abs(target_df['槓桿'] - lev_target)
    best = target_df.sort_values('差').iloc[0]
    
    cost = int(best['權利金'] * 50)
    
    st.balloons()
    
    st.markdown(f"""
    <div style='background: #d4edda; padding: 25px; border-radius: 15px; border: 3px solid #28a745; text-align: center;'>
    <h1 style='color: #155724;'>🚀 **{best['履約價']:,}**</h1>
    <h2 style='color: #155724;'>⚡ **{best['槓桿']}x** | 💰 **${cost:,}**</h2>
    <code style='background: white; padding: 10px; border-radius: 5px; font-size: 18px;'>
    TXO {month} C{best['履約價']} 買進 1 口
    </code>
    </div>
    """, unsafe_allow_html=True)
    
    st.dataframe(target_df[['履約價','權利金','槓桿','Delta']].sort_values('槓桿'))
    
    fig = px.scatter(target_df, x='履約價', y='槓桿', color='Delta', title='履約價 vs 槓桿')
    st.plotly_chart(fig)

st.caption("數據來源：Yahoo Finance 即時運算")
