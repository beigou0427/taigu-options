import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("🔥 台指期權 AI")

# 模擬資料
data = {
    '月份': ['202606', '202606', '202609', '202609'],
    '履約價': [22500, 23000, 22000, 22500],
    '槓桿': [3.2, 2.8, 4.1, 3.5],
    '成本': ['$45,000', '$32,500', '$72,500', '$48,000'],
    '類型': ['CALL ✅', 'CALL ✅', 'CALL ✅', 'CALL ✅']
}

df = pd.DataFrame(data)

st.metric("台指", "23,250")

col1, col2, col3 = st.columns(3)
mode = st.radio("玩法", ["長期", "短期"], horizontal=True, key="mode")
month = st.selectbox("月份", df['月份'].unique())
lev = st.slider("槓桿", 2.0, 15.0, 3.0)

if st.button("🎯 找合約！"):
    filtered = df[df['月份'] == month].sort_values('槓桿')
    best = filtered.iloc[0]
    
    st.success(f"**最佳：{best['履約價']} | {best['槓桿']}x | {best['成本']}**")
    st.dataframe(filtered)
    
    st.balloons()

st.caption("學習版 | 貝伊果屋出品")
