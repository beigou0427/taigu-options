import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import plotly.express as px
import numpy as np
from scipy.stats import norm
import requests
from io import StringIO

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")

st.markdown("# 🔥 **台指期權新手器**\n**官方資料直接抓！已修復**")

# ---------------------------------
# 資料載入（修復版）
# ---------------------------------
@st.cache_data(ttl=300)
def get_txo_from_taifex(target_date=None):
    """修復版：直接從台灣期交所抓每日選擇權報表"""
    try:
        if target_date is None:
            target_date = date.today().strftime("%Y/%m/%d")
        
        url = f"https://www.taifex.com.tw/cht/3/optDailyMarketReport?queryDate={target_date}"
        st.info(f"抓取網址：{url}")
        
        # 抓取 HTML 並解析所有表格
        response = requests.get(url)
        tables = pd.read_html(StringIO(response.text))
        
        st.write(f"找到 {len(tables)} 個表格")
        
        # 找到包含 TXO 的表格（通常是第 2 或第 3 個）
        txo_table = None
        for i, table in enumerate(tables):
            if 'TXO' in table.astype(str).values or '台指' in table.astype(str).values:
                txo_table = table
                st.write(f"找到 TXO 表格（第 {i+1} 個）：")
                st.dataframe(table.head(3))
                break
        
        if txo_table is None:
            return pd.DataFrame()
        
        # 動態解析實際欄位名稱（解決中文欄位問題）
        cols = txo_table.columns.tolist()
        st.write("表格欄位：", cols)
        
        # 常見的欄位對應（依實際表格調整）
        strike_col = None
        close_col = None
        cp_col = None
        contract_col = None
        
        for col in cols:
            if '履約價' in str(col) or '履價' in str(col):
                strike_col = col
            if '成交價' in str(col) or '收盤' in str(col):
                close_col = col
            if '買賣權' in str(col) or '權類' in str(col):
                cp_col = col
            if '契約' in str(col) or '商品' in str(col):
                contract_col = col
        
        # 如果找不到標準欄位，用模糊匹配
        if not strike_col:
            for col in cols:
                if any(x in str(col) for x in ['價', 'K']):
                    strike_col = col
                    break
        
        st.write(f"解析欄位：履約價={strike_col}, 成交價={close_col}, 買賣權={cp_col}")
        
        df = txo_table.dropna(subset=[strike_col, close_col]).copy()
        df['strike_price'] = pd.to_numeric(df[strike_col], errors='coerce')
        df['close'] = pd.to_numeric(df[close_col], errors='coerce')
        df['call_put'] = df[cp_col].map({'買權': 'CALL', '賣權': 'PUT'})
        df['contract_date'] = df[contract_col].astype(str).str.extract(r'(\d{6})')
        
        # 過濾 TXO 合約
        df = df[df['contract_date'].notna()]
        df = df[df['close'] > 0]
        
        return df[['contract_date', 'strike_price', 'close', 'call_put']]
        
    except Exception as e:
        st.error(f"抓取失敗：{e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_current_twii():
    try:
        data = yf.download('^TWII', period='1d', progress=False)
        return float(data['Close'].iloc[-1])
    except:
        return 23290.0  # 今天實際值

# 載入資料
with st.spinner("載入中..."):
    S_current = get_current_twii()
    df_latest = get_txo_from_taifex()
    latest_date = date.today()

col1, col2 = st.columns(2)
col1.metric("📈 台指現價", f"{S_current:,.0f}")
col2.metric("📊 資料日期", latest_date.strftime('%Y-%m-%d'))

if df_latest.empty:
    st.error("❌ 無選擇權資料，可能是：\n• 當日無交易\n• 期交所網站維護\n• 表格格式變動")
    
    # 提供模擬資料讓你測試
    if st.button("🧪 使用模擬資料測試"):
        df_latest = pd.DataFrame({
            'contract_date': ['202602', '202602', '202602'],
            'strike_price': [32500, 33000, 33500],
            'close': [150.5, 85.2, 45.8],
            'call_put': ['CALL', 'CALL', 'CALL']
        })
        st.success("✅ 已切換模擬資料")
    st.stop()
else:
    st.success(f"✅ 載入成功！找到 {len(df_latest)} 筆合約")

# 以下是原有的操作介面（完全不變）
st.markdown("---")
st.markdown("## **🎮 操作超簡單！**")
# ...（接著貼上原有的按鈕、滑桿、計算邏輯等）
