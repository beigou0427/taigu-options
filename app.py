import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import numpy as np
from scipy.stats import norm
from datetime import date

st.set_page_config(layout="wide", page_icon="🔥")
st.markdown("# 🔥 台指期權篩選器")

# 1. 台指現價
@st.cache_data(ttl=60)
def get_price():
    return float(yf.download('^TWII', period='1d')['Close'].iloc[-1])

S = get_price()
st.metric("台指", f"{S:,.0f}")

# 2. 生成合約資料
@st.cache_data
def get_contracts():
    df = pd.DataFrame({
        'month': ['202602', '202603']*8,
        'strike': np.repeat([31000,31500,32000,32500,33000,33500,34000,34500], 2),
        'call_price': [420,285,165,85,35,12,3,1, 285,165,85,35,12,3,1,2],
        'put_price': [1,3,12,35,85,165,285,420, 3,12,35,85,165,285,420,550]
    })
    df['cp'] = ['CALL']*16 + ['PUT']*16
    df['price'] = df['call_price'].where(df['cp']=='CALL', df['put_price'])
    df['month'] = df['month'].iloc[:32]
    return df[['month', 'strike', 'price', 'cp']]

df = get_contracts()
st.success(f"合約數：{len(df)}")

# 3. 篩選介面
col1, col2, col3 = st.columns(3)
with col1: month = st.selectbox("月份", df['month'].unique())
with col2: target_lev = st.slider("目標槓桿", 2, 25, 12)
with col3: cp_type = st.selectbox("類型", ['CALL 📈', 'PUT 📉'])

# 4. 計算
if st.button("🎯 篩選", type="primary"):
    df_filt = df[(df['month']==month) & (df['cp']==('CALL' if 'CALL' in cp_type else 'PUT'))]
    
    df_filt['delta'] = np.clip(np.abs(norm.cdf((np.log(S/df_filt['strike']) + 0.0125)/0.2) * (1 if cp_type=='CALL 📈' else -1)), 0.01, 0.99)
    df_filt['leverage'] = np.abs(df_filt['delta'] * S / df_filt['price'])
    df_filt['cost'] = (df_filt['price'] * 50).round(0)
    df_filt['diff'] = np.abs(df_filt['leverage'] - target_lev)
    
    best = df_filt.nsmallest(1, 'diff').iloc[0]
    
    # 結果
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"""
        ### 🏆 **最佳：{best['strike']:,}**
        **槓桿：{best['leverage']:.1f}x** *(目標 {target_lev}x)*
        **權利金：NT${best['price']:.1f}**
        **成本：${best['cost']:,}**
        
        **下單：** `TXO {month} {cp_type[0]}{best['strike']} 買進 1口`
        """)
    
    with col2:
        st.dataframe(df_filt[['strike', 'price', 'leverage', 'delta', 'cost']].round(1).sort_values('diff').head())
    
    # 圖表
    fig = px.scatter(df_filt, x='strike', y='leverage', color='cp',
                    title=f"{month} {cp_type} 槓桿圖", size='delta')
    fig.add_hline(y=target_lev, line_dash="dash", line_color="red")
    st.plotly_chart(fig)
