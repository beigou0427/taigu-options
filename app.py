"""
🔰 台指期權終極新手機：合約月份自由選！
- 新手教學（超詳細版）
- 數字全開 + 理論價模擬
- CALL / PUT 分開篩選
- 全 FinMind + Black-Scholes + 勝率系統
- 預設開啟「穩健模式」(剔除深價外)
- UI 穩定版 + 嚴肅警慎版 10 大新手建議 (可折疊版)
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from FinMind.data import DataLoader
import numpy as np
from scipy.stats import norm

# =========================
# 新 TOKEN (已更新 2026-02-05)
# =========================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMi0wNSAxODo1ODo1MiIsInVzZXJfaWQiOiJiYWdlbDA0MjciLCJpcCI6IjEuMTcyLjEwOC42OSIsImV4cCI6MTc3MDg5MzkzMn0.cojhPC-1LBEFWqG-eakETyteDdeHt5Cqx-hJ9OIK9k0"

st.set_page_config(page_title="台指期權新手器", layout="wide", page_icon="🔥")
st.markdown("# 🔥 **台指期權新手器**\n**數字全開！含獨家勝率估算！**")

# ---------------------------------
# 🔰 超詳細新手教學區 (收縮版)
# ---------------------------------
with st.expander("📚 **新手村：3分鐘看懂（點我）**", expanded=True):
    st.markdown("""
    ### 🐣 **CALL 📈 vs PUT 📉**
    * **CALL**：覺得台指會**大漲**
    * **PUT**：覺得台指會**大跌**

    ### 💰 **槓桿原理**
    台指漲 1%，你的合約賺 **槓桿倍數**

    ### 📊 **關鍵數字**
    | 名詞 | 意義 |
    |----|----|
    | **履約價** | 約定買賣價格 |
    | **價內(ITM)** | 現在就賺錢 |
    | **Delta** | 跟漲係數 |
    | **🔥勝率** | 獨家估算 |
    """)

# ---------------------------------
# 資料載入
# ---------------------------------
@st.cache_data(ttl=300)
def get_data(token: str):
    if not token: raise ValueError("無 TOKEN")
    dl = DataLoader()
    dl.login
