import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date

st.set_page_config(page_title="台指期權新手機", layout="wide")

st.markdown("""
# 🔥 **台指期權新手機**
**3秒出最佳合約！新手友好**
""")

# 模擬即時資料（雲端版）
S_current = 23250
df_latest = pd.DataFrame({
    'contract_date': [202609, 202609, 202609, 202606, 202606],
    'strike_price': [22000, 22500, 23000, 22500, 23000],
    'close': [85.0, 55.0, 28.0, 45.0, 22.0],
    'call_put': ['CALL', 'CALL', 'CALL', 'CALL', 'CALL']
})

col1.metric("📈 台指", f"{S_current:,}")
col2.metric("📊 更新", "即時")

# 操作區
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("🛡️ 長期", type="primary"):
        st.session_state.mode = 'long'
with col2:
    sel_contract = st.selectbox("📅 月份", df_latest['contract_date'].unique())
with col3:
    target_lev = st.slider("⚡ 槓桿", 1.5, 20.0, 3.0)

if st.button("🎯 找合約！", type="primary"):
    target_df = df_latest[df_latest['contract_date'] == sel_contract]
    
    results = []
    for _, row in target_df.iterrows():
        K = row['strike_price']
        price = row['close']
        leverage = (0.85 * S_current) / price  # 簡化槓桿
        
        results.append({
            '類型': 'CALL 📈',
            '履約價': int(K),
            '權利金': price,
            '槓桿': round(leverage, 1),
            '成本': f"${int(price*50):,}"
        })
    
    df_res = pd.DataFrame(results).sort_values('槓桿', ascending=False)
    best = df_res.iloc[0]
    
    st.balloons()
    st.markdown(f"""
    <div style='background: #d4edda; padding: 25px; border-radius: 15px; border: 3px solid #28a745; text-align: center;'>
    <h1>🚀 **{best['履約價']:,}**</h1>
    <h2>⚡ **{best['槓桿']}x**</h2>
    <h3>💰 **{best['成本']}**</h3>
    <code style='background: white; padding: 15px; font-size: 18px; border-radius: 10px;'>
    TXO {sel_contract}C{best['履約價']} 買進 1 口
    </code>
    </div>
    """, unsafe_allow_html=True)
    
    st.dataframe(df_res)
    
    fig = px.bar(df_res, x='履約價', y='槓桿', title=f'{sel_contract} 槓桿分佈')
    st.plotly_chart(fig)

st.caption("⚠️ 模擬資料版，學習用")
