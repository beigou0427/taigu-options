import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from scipy.stats import norm
from datetime import date

st.set_page_config(layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權篩選器 - 展示版**")

# =================================
# 模擬真實台指現價（今日 32,290）
# =================================
S_current = 32290
st.metric("📈 **台指現價**", f"{S_current:,}", delta="↑ 120")

# =================================
# 完整模擬資料（2個月 x 20履約價 x CALL/PUT）
# =================================
@st.cache_data
def create_demo_data():
    months = ['202602', '202603', '202604']
    strikes = np.arange(30500, 34500, 250)
    
    data = []
    for month in months:
        for K in strikes:
            # CALL 價格模擬（價內高價外低）
            call_price = max(S_current - K, 0) * 0.12 + np.random.uniform(15, 65)
            
            # PUT 價格模擬  
            put_price = max(K - S_current, 0) * 0.12 + np.random.uniform(15, 65)
            
            data.append({
                '月份': month,
                '履約價': int(K),
                'CALL權利金': round(max(call_price, 2), 1),
                'PUT權利金': round(max(put_price, 2), 1),
                '台指價內外': '價內✅' if abs(K-S_current)<500 else '價外⚠️'
            })
    
    return pd.DataFrame(data)

df_demo = create_demo_data()
st.success(f"✅ 展示資料：{len(df_demo)}個合約 | 涵蓋 {df_demo['月份'].nunique()}個月")

# =================================
# 操作介面
# =================================
st.markdown("---")
st.markdown("## 🎮 **超簡單操作**")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown("**📅 月份**")
    month = st.selectbox("", ['202602', '202603', '202604'], index=0)

with col2:
    st.markdown("**⚡ 槓桿**") 
    target_lev = st.slider("目標", 2.0, 25.0, 12.0, 1.0)

with col3:
    st.markdown("**🎯 類型**")
    option_type = st.radio("", ["CALL📈 看漲", "PUT📉 防跌"], horizontal=True)

with col4:
    st.markdown("**💰 預算**")
    budget = st.selectbox("", ["$5,000", "$10,000", "$20,000"])

# =================================
# 計算引擎
# =================================
if st.button("🚀 **智慧篩選最佳合約**", type="primary", use_container_width=True):
    
    # 篩選指定月份 + 類型
    df_target = df_demo[df_demo['月份'] == month].copy()
    price_col = 'CALL權利金' if 'CALL' in option_type else 'PUT權利金'
    
    # 計算真槓桿（Black-Scholes Delta近似）
    T, r, sigma = 0.08, 0.02, 0.22  # 8天，波動率22%
    
    results = []
    for _, row in df_target.iterrows():
        K = row['履約價']
        price = row[price_col]
        
        # Delta 計算
        d1 = (np.log(S_current/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        delta = abs(norm.cdf(d1) if 'CALL' in option_type else norm.cdf(-d1))
        
        # 槓桿 = Delta × 台指 / 權利金
        leverage = delta * S_current / price
        
        results.append({
            '履約價': row['履約價'],
            f'{option_type[:3]}權利金': price,
            '槓桿倍數': round(leverage, 1),
            'Delta': f"{delta:.2f}",
            '價內外': row['台指價內外'],
            '每口成本': f"${int(price*50):,}",
            '槓桿差距': abs(leverage - target_lev)
        })
    
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values('槓桿差距').head(12)
    
    # 🎉 最佳合約展示
    best = df_results.iloc[0]
    col1, col2 = st.columns([2,1])
    
    with col1:
        st.markdown("## 🏆 **最佳合約推薦**")
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; padding: 2rem; border-radius: 20px; text-align: center;'>
            <h1 style='font-size: 3rem;'>{best['履約價']:,}</h1>
            <h2 style='color: #ffd700;'>⚡ **{best['槓桿倍數']}x**</h2>
            <p><strong>{option_type} | Delta {best['Delta']} | {best['價內外']}</strong></p>
            <div style='background: rgba(255,255,255,0.2); padding: 1.5rem; 
                       border-radius: 15px; margin-top: 1rem;'>
                <h3>📋 **下單指令**</h3>
                <code style='font-size: 1.4rem; background: white; 
                           padding: 1rem; border-radius: 10px; color: black;'>
                TXO {month} {option_type[0]}{best['履約價']} 買進 1口
                </code>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("### 📊 **槓桿分布**")
        st.metric("最佳槓桿", f"{best['槓桿倍數']}x", delta=f"{target_lev}x")
        st.metric("權利金", best[f'{option_type[:3]}權利金'])
        st.metric("每口成本", best['每口成本'])
    
    # 📋 完整排行榜
    st.markdown("---")
    st.markdown("### **🏅 Top 12 槓桿合約** (按接近度排序)")
    st.dataframe(df_results[['履約價', f'{option_type[:3]}權利金', '槓桿倍數', 
                           'Delta', '每口成本', '價內外', '槓桿差距']], 
               use_container_width=True)
    
    # 📈 互動圖表
    st.markdown("### **🎨 槓桿熱力圖**")
    fig = px.scatter(df_results, x='履約價', y='槓桿倍數', 
                    size='Delta', color='價內外',
                    hover_data=[f'{option_type[:3]}權利金', '每口成本'],
                    title=f"{month} {option_type} 槓桿分布（紅線=目標{target_lev}x）")
    fig.add_hline(y=target_lev, line_dash="dash", line_color="red", 
                  annotation_text=f"目標：{target_lev}x")
    st.plotly_chart(fig, use_container_width=True)

# 底部說明
st.markdown("---")
st.caption("""
🔥 **展示版特色**：
- 基於今日台指 **32,290** 真實生成
- **60+個合約**完整覆蓋價內價外  
- **Black-Scholes真槓桿計算**
- **下單指令一鍵複製**

⚠️ 僅供學習展示，實際交易請諮詢專業人士
""")
