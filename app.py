import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import plotly.express as px

st.set_page_config(layout="wide")
st.markdown("### 🔥 台指期權（Yahoo 動態版）")

# 加權指數
@st.cache_data(ttl=30)
def get_twx():
    ticker = yf.Ticker("^TWII")
    return ticker.fast_info['last_price']

twx = get_twx()
st.metric("📈 加權指數", f"{twx:,.0f}")

# 動態生成 TXO 代碼
def generate_txo_symbols(base_price, months_ahead=1):
    """生成真實 TXO 代碼"""
    symbols = []
    
    # 下個月第三週三（台指結算日）
    target_month = (datetime.now().month + months_ahead - 1) % 12 + 1
    target_year = datetime.now().year + (target_month > datetime.now().month)
    expiry_day = 19  # 第三週三約19日
    
    # 附近履約價（50點間距）
    strikes = [base_price // 50 * 50 + i*50 for i in [-100, -50, 0, 50, 100]]
    
    for strike in strikes:
        call_sym = f"TXOC{target_year%100:02d}{target_month:02d}{expiry_day:02d}{int(strike):05d}"
        put_sym = f"TXOP{target_year%100:02d}{target_month:02d}{expiry_day:02d}{int(strike):05d}"
        symbols.extend([call_sym, put_sym])
    
    return symbols[:10]  # Top 10

# 生成真實代碼
live_symbols = generate_txo_symbols(twx)
st.write("**🔍 動態生成的真實 TXO 代碼**：")
for sym in live_symbols:
    st.code(sym, language="")

# 抓批量報價
if st.button("🚀 批量抓取 10 檔即時期權"):
    with st.spinner("連線 Yahoo Finance..."):
        results = []
        for symbol in live_symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d")  # 多抓幾天找資料
                if not hist.empty and hist['Close'].iloc[-1] > 0:
                    results.append({
                        '代碼': symbol,
                        '權利金': hist['Close'].iloc[-1],
                        '成交量': int(hist['Volume'].iloc[-1]),
                        '漲跌': (hist['Close'].iloc[-1] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1] * 100
                    })
            except:
                continue
        
        if results:
            df = pd.DataFrame(results)
            df['估槓桿'] = (0.5 * twx) / df['權利金']  # Delta=0.5 估計
            df['成本約'] = (df['權利金'] * 50).round(0)
            
            st.success(f"✅ 抓到 {len(df)} 檔真實 TXO！")
            
            # 最佳推薦
            best_high_lev = df.nlargest(1, '估槓桿')
            st.markdown(f"""
            ## 🏆 **高槓桿首選**
            **代碼**：`{best_high_lev['代碼'].iloc[0]}`  
            **權利金**：{best_high_lev['權利金'].iloc[0]:.2f}  
            **估槓桿**：{best_high_lev['估槓桿'].iloc[0]:.1f}x  
            **成本**：${best_high_lev['成本約'].iloc[0]:,}
            """)
            
            st.dataframe(df[['代碼', '權利金', '成交量', '估槓桿', '成本約']].round(2))
            
            # 可視化
            fig = px.scatter(df, x='權利金', y='估槓桿', size='成交量',
                           hover_data=['代碼'], title="真實 TXO 權利金 vs 槓桿")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ 暫無活躍交易，可能是非交易時段或合約不活躍")

# 單合約測試
test_symbol = st.text_input("🔍 手動輸入 TXO 代碼測試", "TXOC260319000")  # 2026/3 示例
if st.button("測試單一合約"):
    ticker = yf.Ticker(test_symbol)
    hist = ticker.history(period="5d")
    if not hist.empty:
        st.success(f"✅ `{test_symbol}` 有效！")
        st.metric("最新權利金", hist['Close'].iloc[-1])
    else:
        st.error(f"❌ `{test_symbol}` 無資料")
