import streamlit as st
import pandas as pd
import numpy as np
from datetime import date

st.set_page_config(layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權篩選器**")

# 台指現價
S_current = 32290
st.metric("📈 **台指現價**", f"{S_current:,}")

# 模擬資料
@st.cache_data
def create_demo_data():
    months = ['202602', '202603']
    data = []
    
    for month in months:
        # 真實履約價範圍
        for K in [31000, 31250, 31500, 31750, 32000, 32250, 32500, 32750, 33000, 33250, 33500]:
            # CALL
            call_price = max(S_current - K, 0) * 0.15 + np.random.uniform(20, 60)
            # PUT  
            put_price = max(K - S_current, 0) * 0.15 + np.random.uniform(20, 60)
            
            data.append({
                '月份': month,
                '履約價': K,
                'CALL': round(max(call_price, 5), 1),
                'PUT': round(max(put_price, 5), 1),
            })
    return pd.DataFrame(data)

df = create_demo_data()

# 操作介面
st.markdown("---")
st.markdown("### 🎮 **篩選條件**")
col1, col2, col3 = st.columns(3)

with col1:
    month = st.selectbox("📅 月份", ['202602', '202603'])

with col2:
    target_lev = st.slider("⚡ 目標槓桿", 3.0, 20.0, 10.0, 1.0)

with col3:
    option_type = st.radio("類型", ["CALL📈", "PUT📉"])

if st.button("🎯 **找最佳合約**", type="primary", use_container_width=True):
    
    # 篩選
    df_target = df[df['月份'] == month].copy()
    price_col = 'CALL' if 'CALL' in option_type else 'PUT'
    
    # 計算槓桿
    results = []
    for _, row in df_target.iterrows():
        K = row['履約價']
        price = row[price_col]
        
        # 簡化槓桿計算
        if abs(K - S_current) < 1000:
            delta = 0.6
        elif abs(K - S_current) < 2000:
            delta = 0.4  
        else:
            delta = 0.2
            
        leverage = delta * S_current / price
        
        results.append({
            '履約價': f"{row['履約價']:,}",
            '權利金': price,
            '槓桿': f"{leverage:.1f}x",
            '每口成本': f"${int(price*50):,}",
            '差距': abs(leverage - target_lev)
        })
    
    df_results = pd.DataFrame(results).sort_values('差距').head(8)
    best = df_results.iloc[0]
    
    # 最佳合約卡片
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white; padding: 2rem; border-radius: 15px; text-align: center;'>
        <h1 style='font-size: 3rem;'>{best['履約價']}</h1>
        <h2 style='color: #ffd700;'>⚡ **{best['槓桿']}**</h2>
        <p><strong>{option_type} | {best['每口成本']}</strong></p>
        <div style='background: rgba(255,255,255,0.2); padding: 1rem; border-radius: 10px;'>
            <code style='font-size: 1.3rem;'>TXO {month} {option_type[0]}{best['履約價'].replace(',','')} 買進 1口</code>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Top 8 表格
    st.markdown("### 🏅 **最佳 8 個合約** (按槓桿接近度排序)")
    st.dataframe(df_results, use_container_width=True)

st.caption("⚠️ 模擬展示用，實際交易請諮詢專業人士")
