import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from scipy.stats import norm
from datetime import date

st.set_page_config(layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權篩選器**")

# 台指現價
S_current = 32290
st.metric("📈 **台指現價**", f"{S_current:,}")

# 模擬資料
@st.cache_data
def create_demo_data():
    months = ['202602', '202603', '202604']
    strikes = np.arange(30500, 34500, 250)
    
    data = []
    for month in months:
        for K in strikes:
            call_price = max(S_current - K, 0) * 0.12 + np.random.uniform(15, 65)
            put_price = max(K - S_current, 0) * 0.12 + np.random.uniform(15, 65)
            
            data.append({
                '月份': month,
                '履約價': int(K),
                'CALL權利金': round(max(call_price, 2), 1),
                'PUT權利金': round(max(put_price, 2), 1),
            })
    return pd.DataFrame(data)

df_demo = create_demo_data()

# 操作介面
st.markdown("---")
st.markdown("## 🎮 **操作**")
col1, col2, col3 = st.columns(3)

with col1:
    month = st.selectbox("📅 月份", ['202602', '202603', '202604'])

with col2:
    target_lev = st.slider("⚡ 目標槓桿", 2.0, 25.0, 12.0, 1.0)

with col3:
    option_type = st.radio("🎯 類型", ["CALL📈", "PUT📉"])

# 計算
if st.button("🚀 **找最佳合約**", type="primary", use_container_width=True):
    
    df_target = df_demo[df_demo['月份'] == month].copy()
    price_col = 'CALL權利金' if 'CALL' in option_type else 'PUT權利金'
    
    # 槓桿計算
    results = []
    for _, row in df_target.iterrows():
        K = row['履約價']
        price = row[price_col]
        
        # 簡化 Delta
        delta = abs(0.5 + 0.5 * np.tanh((S_current - K) / 1000))
        leverage = delta * S_current / price
        
        results.append({
            '履約價': row['履約價'],
            '權利金': price,
            '槓桿': round(leverage, 1),
            'Delta': f"{delta:.2f}",
            '每口成本': f"${int(price*50):,}",
            '差距': abs(leverage - target_lev)
        })
    
    df_results = pd.DataFrame(results).sort_values('差距').head(10)
    best = df_results.iloc[0]
    
    # 最佳合約
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white; padding: 2rem; border-radius: 15px; text-align: center;'>
        <h1 style='font-size: 3rem;'>{best['履約價']:,}</h1>
        <h2 style='color: #ffd700;'>⚡ **{best['槓桿']}x**</h2>
        <p><strong>{option_type} | {best['每口成本']}</strong></p>
        <div style='background: rgba(255,255,255,0.2); padding: 1rem; border-radius: 10px;'>
            <code style='font-size: 1.3rem;'>TXO {month} {option_type[0]}{best['履約價']} 買進 1口</code>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 排行榜
    st.markdown("### 🏅 **Top 10 合約**")
    st.dataframe(df_results, use_container_width=True)
    
    # 散點圖（非熱力圖）
    st.markdown("### 📊 **槓桿分布**")
    fig = px.scatter(df_results, x='履約價', y='槓桿', 
                     size_max=20, title=f"{month} {option_type} 槓桿圖")
    fig.add_hline(y=target_lev, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

st.caption("⚠️ 模擬展示用，實際交易請諮詢專業人士")
