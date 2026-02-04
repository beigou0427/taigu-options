import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.markdown("""
# 🔥 **台指期權 AI**
**3秒出最佳合約！新手友好**
""")

# 固定台指價格（避免 yfinance 問題）
S_current = 23250.0

# 完整模擬資料
contracts = {
    202606: {'CALL': [22000, 22500, 23000], 'prices': [75, 48, 25]},
    202609: {'CALL': [21500, 22000, 22500, 23000], 'prices': [95, 72, 48, 25]},
    202612: {'CALL': [21000, 22000, 23000], 'prices': [115, 85, 35]}
}

col1.metric("📈 台指", f"{S_current:,}")
col2.metric("📊 即時", "2026/2/4")

# 操作
col1, col2, col3 = st.columns(3)

with col1:
    mode = st.radio("玩法", ["🛡️ 長期", "⚡ 短期"], horizontal=True)
with col2:
    sel_contract = st.selectbox("📅 月份", list(contracts.keys()))
with col3:
    target_lev = st.slider("⚡ 槓桿", 1.5, 20.0, 3.0)

if st.button("🎯 **找最佳合約！**", type="primary"):
    
    # 資料
    calls = contracts[sel_contract]['CALL']
    prices = contracts[sel_contract]['prices']
    
    results = []
    for i, (K, price) in enumerate(zip(calls, prices)):
        leverage = max(1.5, min(25, (0.85 * S_current) / price))
        results.append({
            '類型': 'CALL 📈',
            '履約價': K,
            '權利金': f"{price:.1f}",
            '槓桿': f"{leverage:.1f}x",
            '成本': f"${int(price*50):,}",
            '價內': '✅' if K <= S_current else '⚠️'
        })
    
    df_res = pd.DataFrame(results)
    df_res['lev_num'] = df_res['槓桿'].str.extract('(\\d+\\.?)\\d*').astype(float)
    df_res = df_res.sort_values('lev_num', key=lambda x: abs(x - target_lev))
    
    best = df_res.iloc[0]
    
    st.balloons()
    
    # 最佳推薦
    st.markdown("""
    ## 🎉 **最佳合約！直接下單！**
    """)
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #d4edda, #c3e6cb); padding: 30px; 
                border-radius: 20px; border: 4px solid #28a745; text-align: center;'>
    <h1 style='color: #155724;'>🚀 **{best['履約價']:,}**</h1>
    <h2 style='color: #155724;'>⚡ **{best['槓桿']}** | 💰 **{best['成本']}**</h2>
    <h3>📋 下單指令：</h3>
    <code style='background: white; padding: 20px; font-size: 20px; border-radius: 15px; display: block;'>
    TXO {sel_contract}C{best['履約價']} 買進 1 口
    </code>
    <p style='color: #155724; font-size: 18px;'>{best['價內']} {best['類型']}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 表格
    st.markdown("## 📋 所有合約")
    st.dataframe(df_res[['類型','履約價','權利金','槓桿','成本','價內']], use_container_width=True)
    
    # 圖表
    fig = px.bar(df_res, x='履約價', y='槓桿', title=f'{sel_contract} 槓桿分佈')
    st.plotly_chart(fig)

st.caption("✅ **雲端完美版** | 學習用 | 真實交易請用券商資料")
