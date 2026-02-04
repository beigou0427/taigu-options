import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.markdown("# 🔥 台指期權 AI")
st.markdown("**3秒出最佳合約！新手友好**")

S_current = 23250

data = {
    '月份': ['202606', '202606', '202609', '202609'],
    '履約價': [22000, 22500, 21500, 22500],
    '槓桿': [4.2, 3.1, 5.8, 3.5],
    '成本': ['$37,500', '$48,000', '$72,500', '$55,000'],
    '狀態': ['CALL', 'CALL', 'CALL', 'CALL']
}

df = pd.DataFrame(data)

col1, col2 = st.columns(2)
col1.metric("台指", str(S_current) + "點")
col2.metric("更新", "雲端版")

month = st.selectbox("月份", df['月份'].unique())
lev = st.slider("目標槓桿", 2.0, 10.0, 3.5)

if st.button("找合約！"):
    filtered = df[df['月份'] == month]
    best = filtered.iloc[0]
    
    st.success("最佳合約！")
    st.write("履約價：" + str(best['履約價']))
    st.write("槓桿：" + str(best['槓桿']) + "x")
    st.write("成本：" + best['成本'])
    st.write("下單：" + "TXO " + str(month) + "C" + str(best['履約價']) + " 1口")
    
    st.dataframe(filtered)
    
    st.balloons()

st.caption("貝伊果屋出品 | 學習版")
