import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title="台指期權 AI（真實合約）", layout="wide", page_icon="🔥")

st.markdown("""
# 🔥 台指期權 AI（真實合約）
**全部數字都來自 TAIFEX OpenAPI；抓不到就停止，不猜。**
""")

BASE = "https://openapi.taifex.com.tw/v1"

def _fail(title: str, detail: str, extra: str = ""):
    st.error(f"❌ {title}\n\n{detail}")
    if extra:
        st.code(extra)
    st.stop()

@st.cache_data(ttl=60)
def fetch_json_strict(path: str):
    url = f"{BASE}{path}"
    try:
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=20)
    except Exception as e:
        _fail("連線失敗", f"{url}\n{repr(e)}")

    if r.status_code != 200:
        _fail("HTTP 非 200", f"{url}\nstatus={r.status_code}", r.text[:1000])

    ctype = (r.headers.get("content-type") or "").lower()
    if "json" not in ctype:
        # 常見：回了 text/csv 或 html（WAF / 502 / 轉址），這時 json() 一定會爆
        _fail("回傳不是 JSON", f"{url}\ncontent-type={ctype}", r.text[:1000])

    try:
        data = r.json()
    except Exception as e:
        _fail("JSON 解析失敗", f"{url}\n{repr(e)}", r.text[:1000])

    if not data:
        _fail("JSON 是空的", f"{url}")
    if not isinstance(data, list):
        _fail("JSON 不是 list", f"{url}\n實際型別={type(data)}", str(data)[:1000])
    return data

def pick_col(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def pick_col_contains(df: pd.DataFrame, keyword: str):
    keyword = keyword.lower()
    hits = [c for c in df.columns if keyword in str(c).lower()]
    return hits[0] if hits else None

def normalize_cp(s: str):
    t = str(s).strip().upper()
    if t in ["C", "CALL", "買權"]:
        return "CALL"
    if t in ["P", "PUT", "賣權"]:
        return "PUT"
    return t

with st.spinner("連線 TAIFEX OpenAPI（期貨/選擇權/Delta）…"):
    # 期貨每日行情（用 TXF 當作標的價）
    fut_raw = fetch_json_strict("/DailyMarketReportFut")   # 正確路徑之一 [web:412]
    # 選擇權每日行情（權利金/成交量/未平倉）
    opt_raw = fetch_json_strict("/DailyMarketReportOpt")   # 正確路徑之一 [web:412]
    # 選擇權每日 Delta
    dlt_raw = fetch_json_strict("/DailyOptionsDelta")      # 正確路徑之一 [web:412]

df_fut = pd.DataFrame(fut_raw)
df_opt = pd.DataFrame(opt_raw)
df_dlt = pd.DataFrame(dlt_raw)

# ---- 欄位自動對應（對不上就停）----
# 共同：商品代號
col_sym_f = pick_col(df_fut, ["商品代號", "Symbol", "symbol", "InstrumentID", "Contract", "商品"])
col_sym_o = pick_col(df_opt, ["商品代號", "Symbol", "symbol", "InstrumentID", "Contract", "商品"])
col_sym_d = pick_col(df_dlt, ["商品代號", "Symbol", "symbol", "InstrumentID", "Contract", "商品"])

if not col_sym_f or not col_sym_o or not col_sym_d:
    _fail("欄位找不到：商品代號", f"fut={col_sym_f}, opt={col_sym_o}, delta={col_sym_d}",
          f"fut cols={list(df_fut.columns)}\nopt cols={list(df_opt.columns)}\ndelta cols={list(df_dlt.columns)}")

# 選擇權必要欄位：合約月份、履約價、買賣權、收盤價
col_month_o = pick_col(df_opt, ["到期月份(週別)", "ContractMonth", "contract_date", "到期月份", "Contract_Month"])
col_strike_o = pick_col(df_opt, ["履約價", "StrikePrice", "strike_price", "Strike_Price"])
col_cp_o = pick_col(df_opt, ["買賣權", "CallPut", "call_put", "CallPutPair", "CP"])
col_close_o = pick_col(df_opt, ["收盤價", "ClosePrice", "close", "Close", "最後成交價", "LastPrice"])
if not all([col_month_o, col_strike_o, col_cp_o, col_close_o]):
    _fail("欄位找不到：選擇權必要欄位",
          f"month={col_month_o}, strike={col_strike_o}, cp={col_cp_o}, close={col_close_o}",
          f"opt cols={list(df_opt.columns)}")

# Delta 必要欄位：合約月份、履約價、買賣權、Delta
col_month_d = pick_col(df_dlt, ["到期月份(週別)", "ContractMonth", "contract_date", "到期月份", "Contract_Month"])
col_strike_d = pick_col(df_dlt, ["履約價", "StrikePrice", "strike_price", "Strike_Price"])
col_cp_d = pick_col(df_dlt, ["買賣權", "CallPut", "call_put", "CallPutPair", "CP"])
col_delta = pick_col(df_dlt, ["Delta", "delta"])
if not col_delta:
    col_delta = pick_col_contains(df_dlt, "delta")
if not all([col_month_d, col_strike_d, col_cp_d, col_delta]):
    _fail("欄位找不到：Delta 必要欄位",
          f"month={col_month_d}, strike={col_strike_d}, cp={col_cp_d}, delta={col_delta}",
          f"delta cols={list(df_dlt.columns)}")

# 期貨：合約月份 + 收盤或結算（用來當標的 S）
col_month_f = pick_col(df_fut, ["到期月份", "ContractMonth", "contract_date", "到期月份(週別)"])
col_close_f = pick_col(df_fut, ["收盤價", "ClosePrice", "close", "Close"])
col_settle_f = pick_col(df_fut, ["結算價", "SettlementPrice", "settlement_price"])
if not col_month_f:
    _fail("欄位找不到：期貨合約月份", f"fut month col not found", f"fut cols={list(df_fut.columns)}")
if not (col_close_f or col_settle_f):
    _fail("欄位找不到：期貨收盤/結算", f"close={col_close_f}, settle={col_settle_f}", f"fut cols={list(df_fut.columns)}")

# ---- 資料過濾：只要 TXO / TXF ----
df_opt = df_opt[df_opt[col_sym_o].astype(str).str.contains("TXO", na=False)].copy()
df_dlt = df_dlt[df_dlt[col_sym_d].astype(str).str.contains("TXO", na=False)].copy()
df_fut = df_fut[df_fut[col_sym_f].astype(str).str.contains("TXF", na=False)].copy()

if df_opt.empty or df_dlt.empty or df_fut.empty:
    _fail("過濾 TXO/TXF 後是空的",
          f"opt_rows={len(df_opt)}, delta_rows={len(df_dlt)}, fut_rows={len(df_fut)}",
          "請檢查 Symbol/商品代號欄位內容是否真的含 TXO / TXF")

# ---- 型別整理 ----
df_opt[col_strike_o] = pd.to_numeric(df_opt[col_strike_o], errors="coerce")
df_opt[col_close_o] = pd.to_numeric(df_opt[col_close_o], errors="coerce")
df_opt[col_cp_o] = df_opt[col_cp_o].apply(normalize_cp)

df_dlt[col_strike_d] = pd.to_numeric(df_dlt[col_strike_d], errors="coerce")
df_dlt[col_delta] = pd.to_numeric(df_dlt[col_delta], errors="coerce")
df_dlt[col_cp_d] = df_dlt[col_cp_d].apply(normalize_cp)

price_col_f = col_close_f if col_close_f else col_settle_f
df_fut[price_col_f] = pd.to_numeric(df_fut[price_col_f], errors="coerce")

df_opt = df_opt.dropna(subset=[col_strike_o, col_close_o])
df_opt = df_opt[df_opt[col_close_o] > 0].copy()

df_dlt = df_dlt.dropna(subset=[col_strike_d, col_delta])
df_fut = df_fut.dropna(subset=[col_month_f, price_col_f]).copy()

# ---- 合約月份選單：完全由真實資料決定（不會出現不存在的月份）----
months = sorted(set(df_opt[col_month_o].astype(str).unique()) & set(df_dlt[col_month_d].astype(str).unique()))
if not months:
    _fail("找不到可用月份（opt 與 delta 無交集）",
          f"opt months={sorted(df_opt[col_month_o].astype(str).unique())}\ndelta months={sorted(df_dlt[col_month_d].astype(str).unique())}")

# ---- UI ----
colA, colB, colC = st.columns(3)

with colA:
    sel_month = st.selectbox("📅 真實合約月份", months)

with colB:
    direction = st.radio("方向", ["CALL", "PUT"], horizontal=True)

with colC:
    target_lev = st.slider("目標槓桿（用 Delta 計算）", 1.5, 25.0, 5.0, 0.5)

# 標的價：用同月份 TXF 的收盤/結算；找不到就停（不猜）
df_fut_m = df_fut[df_fut[col_month_f].astype(str) == str(sel_month)].copy()
if df_fut_m.empty:
    _fail("找不到對應月份的 TXF", f"選擇的月份={sel_month}\nTXF 可用月份={sorted(df_fut[col_month_f].astype(str).unique())}")

S = float(df_fut_m[price_col_f].dropna().iloc[0])

st.metric("TXF（真實）收盤/結算", f"{S:,.0f}", f"來源欄位：{price_col_f}")

# 合併 opt + delta（同月份、同履約價、同 CP）
opt_m = df_opt[df_opt[col_month_o].astype(str) == str(sel_month)].copy()
dlt_m = df_dlt[df_dlt[col_month_d].astype(str) == str(sel_month)].copy()

opt_m = opt_m[opt_m[col_cp_o] == direction].copy()
dlt_m = dlt_m[dlt_m[col_cp_d] == direction].copy()

merged = opt_m.merge(
    dlt_m,
    left_on=[col_strike_o, col_cp_o],
    right_on=[col_strike_d, col_cp_d],
    how="inner",
    suffixes=("_opt", "_dlt"),
)

if merged.empty:
    _fail("合併 opt + delta 後為空",
          f"month={sel_month}, direction={direction}\n"
          f"opt rows={len(opt_m)}, delta rows={len(dlt_m)}\n"
          f"join keys: opt({col_strike_o},{col_cp_o}) delta({col_strike_d},{col_cp_d})")

# 計算槓桿：Leverage = |Delta| * S / 權利金（權利金用真實收盤價）
merged["權利金"] = pd.to_numeric(merged[col_close_o], errors="coerce")
merged["Delta"] = pd.to_numeric(merged[col_delta], errors="coerce")
merged = merged.dropna(subset=["權利金", "Delta"])
merged = merged[merged["權利金"] > 0].copy()
merged["槓桿"] = (merged["Delta"].abs() * S) / merged["權利金"]
merged["成本(約)"] = (merged["權利金"] * 50).round(0).astype(int)

merged["差距"] = (merged["槓桿"] - float(target_lev)).abs()
merged = merged.sort_values("差距", ascending=True)

best = merged.iloc[0]

st.markdown("## 🎯 真實合約推薦")
st.markdown(
    f"- 月份：{sel_month}\n"
    f"- 類型：{direction}\n"
    f"- 履約價：{int(best[col_strike_o])}\n"
    f"- 權利金（收盤）：{best['權利金']}\n"
    f"- Delta（TAIFEX）：{best['Delta']}\n"
    f"- 槓桿：{best['槓桿']:.2f}x\n"
    f"- 成本（約）：${best['成本(約)']:,}"
)

st.markdown("## 📋 真實合約清單（Top 50）")
show_cols = {
    "履約價": col_strike_o,
    "權利金(收盤)": "權利金",
    "Delta": "Delta",
    "槓桿": "槓桿",
    "成本(約)": "成本(約)",
}
show_df = merged[list(show_cols.values())].rename(columns={v: k for k, v in show_cols.items()}).head(50)
st.dataframe(show_df, use_container_width=True)

fig = px.scatter(show_df, x="履約價", y="槓桿", size="權利金(收盤)", title="履約價 vs 槓桿（真實收盤 + 真實 Delta）")
fig.add_hline(y=float(target_lev), line_dash="dash")
st.plotly_chart(fig, use_container_width=True)

st.caption("註：以上為 TAIFEX OpenAPI 每日行情/每日 Delta（盤後資料）。")
