import streamlit as st
import pandas as pd

st.set_page_config(page_title="台指期權AI", layout="wide")

st.markdown("""
# 🔥 **台指期權 AI**
**3秒出最佳合約**
""")

S_current = 23250

data = {
    '月份': ['202606', '202606', '202609', '202609', '202612'],
    '履約價': [22000, 22500, 21500, 22500, 22000],
    '槓桿': [4.2, 3.1, 5.8, 3.5, 4.5],
    '成本': ['$37,500', '$48,000', '$72,500', '$55,000', '$42,500'],
    '狀態': ['CALL ✅', 'CALL ✅', 'CALL ✅', 'CALL ✅', 'CALL ✅']
}

df = pd.DataFrame(data)

col1, col2 = st.columns(2)
col1.metric("📈 台指", f"{S_current:,}")
col2.metric("📱 即時", "雲端版")

# 操作
month = st.selectbox("📅 月份", df['月份'].unique())
lev = st.slider("⚡ 目標槓桿", 2.0, 10.0, 3.5)

if st.button("🎯 **找合約！**", type="primary"):
    filtered = df[df['月份'] == month].sort_values('槓桿')
    best = filtered.iloc[(filtered['槓桿'] - lev).abs().argsort()[:1]].iloc[0]
    
    st.balloons()
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #d4edda, #c3e6cb); 
                padding: 30px; border-radius: 20px; border: 4px solid #28a745; 
                text-align
