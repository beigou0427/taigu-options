import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
from FinMind.data import DataLoader
from scipy.stats import norm

# =============================
# 1. 基本設定
# =============================
st.set_page_config(page_title="CALL獵人 - LEAPS 掃描器", layout="wide", page_icon="📈")

try:
    FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", st.secrets.get("finmind_token", ""))
    st.info(f"🔑 Token 狀態: {'✅ 已設定' if FINMIND_TOKEN else '❌ 未設定'}")
    if not FINMIND_TOKEN:
        st.error("🚨 請在 .streamlit/secrets.toml 加: FINMIND_TOKEN = '你的token'")
except Exception as e:
    st.error(f"Secrets 讀取失敗: {str(e)[:50]}...")
    FINMIND_TOKEN = ""

for k, v in {
    "call_res": [],
    "call_best": None,
    "call_pf": [],
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =============================
# 2. 共用函數（從原本程式搬過來）
# =============================
@st.cache_data(ttl=60)
def get_option_data(token):
    dl = DataLoader()
    if token:
        dl.login_by_token(api_token=token)
    try:
        index_df = dl.taiwan_stock_daily(
            "TAIEX",
            start_date=(date.today() - timedelta(days=100)).strftime("%Y-%m-%d"),
        )
        S = float(index_df["close"].iloc[-1]) if not index_df.empty else 23000.0
    except:
        S = 23000.0

    opt_start = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
    df = dl.taiwan_option_daily("TXO", start_date=opt_start)
    if df.empty:
        return S, pd.DataFrame(), pd.to_datetime(date.today())

    df["date"] = pd.to_datetime(df["date"])
    latest = df["date"].max()
    return S, df[df["date"] == latest].copy(), latest

def calculate_raw_score(delta, days, vol, S_current, K, op_type):
    # 直接貼你原本的 scoring 公式
    score = abs(delta) * 100 + np.log1p(vol) * 5 + days * 0.05
    if op_type == "CALL" and K >= S_current:
        score += 10
    return score

def micro_expand_scores(raw_results):
    # 這裡簡化：把 raw_score 線性轉成勝率，你可以貼回原本那套
    out = []
    for r in raw_results:
        base = r["raw_score"]
        win = max(min(50 + (base - 50) * 0.3, 99), 1)
        r["勝率"] = win
        out.append(r)
    return out

# =============================
# 3. UI：標題 & 資料載入
# =============================
st.markdown("# 📈 CALL獵人 (LEAPS 掃描器)")
st.caption("輸入目標槓桿，一鍵幫你找出最適合的 TXO 長天期選擇權。")

with st.spinner("載入最新 TXO 選擇權資料中..."):
    S_current, df_latest, latest_date = get_option_data(FINMIND_TOKEN)

if df_latest.empty:
    st.error("無法取得 TXO 資料，請稍後再試或檢查 FinMind Token。")
    st.stop()

st.info(f"今日加權指數估計：{S_current:,.0f}，期權資料日期：{latest_date.date()}")

df_work = df_latest.copy()

# =============================
# 4. 控制區：方向 / 月份 / 槓桿
# =============================
col_ctrl, col_pf = st.columns([2, 1])

with col_ctrl:
    c1, c2, c3, c4 = st.columns([1, 1, 1, 0.6])
    with c1:
        dir_mode = st.selectbox("方向", ["📈 CALL (LEAPS)", "📉 PUT"], 0)
        op_type = "CALL" if "CALL" in dir_mode else "PUT"
    with c2:
        contracts = df_work[df_work["call_put"] == op_type]["contract_date"].dropna()
        available = sorted(contracts[contracts.astype(str).str.len() == 6].unique())
        default_idx = len(available) - 1 if available else 0
        sel_con = st.selectbox("月份", available if available else [""], index=default_idx)
    with c3:
        target_lev = st.slider("目標槓桿", 2.0, 20.0, 5.0, 0.5)
    with c4:
        if st.button("🧹 重置"):
            st.session_state["call_res"] = []
            st.session_state["call_best"] = None
            st.session_state["call_pf"] = []
            st.rerun()

    if st.button("🚀 執行掃描", type="primary", use_container_width=True):
        st.session_state["call_res"] = []
        st.session_state["call_best"] = None

        if sel_con and len(str(sel_con)) == 6:
            tdf = df_work[
                (df_work["contract_date"].astype(str) == sel_con)
                & (df_work["call_put"] == op_type)
            ]

            if tdf.empty:
                st.warning("無資料")
            else:
                try:
                    y, m = int(str(sel_con)[:4]), int(str(sel_con)[4:6])
                    days = max((date(y, m, 15) - latest_date.date()).days, 1)
                    T = days / 365.0
                except:
                    st.error("日期解析失敗")
                    st.stop()

                raw_results = []
                for _, row in tdf.iterrows():
                    try:
                        K = float(row["strike_price"])
                        vol = float(row["volume"])
                        close_p = float(row["close"])
                        if K <= 0:
                            continue

                        try:
                            r, sigma = 0.02, 0.2
                            d1 = (np.log(S_current / K) + (r + 0.5 * sigma**2) * T) / (
                                sigma * np.sqrt(T)
                            )
                            if op_type == "CALL":
                                delta = norm.cdf(d1)
                                bs_p = S_current * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(
                                    d1 - sigma * np.sqrt(T)
                                )
                            else:
                                delta = -norm.cdf(-d1)
                                bs_p = K * np.exp(-r * T) * norm.cdf(
                                    -(d1 - sigma * np.sqrt(T))
                                ) - S_current * norm.cdf(-d1)
                        except:
                            delta, bs_p = 0.5, close_p

                        P = close_p if vol > 0 else bs_p
                        if P <= 0.5:
                            continue

                        lev = (abs(delta) * S_current) / P
                        if abs(delta) < 0.1:
                            continue

                        raw_score = calculate_raw_score(delta, days, vol, S_current, K, op_type)
                        status = "🟢成交" if vol > 0 else "🔵合理"

                        raw_results.append(
                            {
                                "履約價": int(K),
                                "價格": P,
                                "狀態": status,
                                "槓桿": lev,
                                "Delta": delta,
                                "raw_score": raw_score,
                                "Vol": int(vol),
                                "差距": abs(lev - target_lev),
                                "合約": sel_con,
                                "類型": op_type,
                                "天數": days,
                            }
                        )
                    except:
                        continue

                if raw_results:
                    final_results = micro_expand_scores(raw_results)
                    final_results.sort(key=lambda x: (x["差距"], -x["勝率"], -x["天數"]))
                    st.session_state["call_res"] = final_results[:15]
                    st.session_state["call_best"] = final_results[0]
                    st.success(f"掃描完成！最佳槓桿：{final_results[0]['槓桿']:.1f}x")
                else:
                    st.warning("無符合資料")

    # 結果區
    if st.session_state["call_res"]:
        best = st.session_state["call_best"]
        st.markdown("---")
        cA, cB = st.columns([2, 1])
        with cA:
            st.markdown("#### 🏆 最佳推薦")
            p_int = int(round(best["價格"]))
            st.markdown(
                f"`{best['合約']} {best['履約價']} {best['類型']}` **{p_int}點**  \n"
                f"槓桿 `{best['槓桿']:.1f}x` | 勝率 `{best['勝率']:.1f}%` | 天數 `{best.get('天數', 0)}天`"
            )
        with cB:
            if st.button("➕ 加入投組"):
                exists = any(
                    p["履約價"] == best["履約價"] and p["合約"] == best["合約"]
                    for p in st.session_state["call_pf"]
                )
                if not exists:
                    st.session_state["call_pf"].append(best)
                    st.toast("✅ 已加入投組")
                else:
                    st.toast("⚠️ 已存在")

        with st.expander("📋 搜尋結果 (依槓桿→勝率→天數排序)", expanded=True):
            df_show = pd.DataFrame(st.session_state["call_res"]).copy()
            df_show["權利金"] = df_show["價格"].round(0).astype(int)
            df_show["槓桿"] = df_show["槓桿"].map(lambda x: f"{x:.1f}x")
            df_show["Delta"] = df_show["Delta"].map(lambda x: f"{x:.2f}")
            df_show["勝率"] = df_show["勝率"].map(lambda x: f"{x:.1f}%")
            df_show["天數"] = df_show.get("天數", 0).astype(int)
            cols = ["合約", "履約價", "權利金", "槓桿", "勝率", "天數", "差距"]
            st.dataframe(df_show[cols], use_container_width=True, hide_index=True)

# =============================
# 5. 投組區
# =============================
with col_pf:
    st.markdown("#### 💼 LEAPS CALL 投組")
    if st.session_state["call_pf"]:
        pf = pd.DataFrame(st.session_state["call_pf"])
        total = pf["價格"].sum() * 50
        avg_win = pf["勝率"].mean()
        avg_lev = pf["槓桿"].mean()

        st.metric("總權利金", f"${int(total):,}")
        st.caption(f"{len(pf)}口 | Avg槓桿 {avg_lev:.1f}x | Avg勝率 {avg_win:.1f}%")

        pf_s = pf.copy()
        pf_s["權利金"] = pf_s["價格"].round(0).astype(int)
        pf_s["Delta"] = pf_s["Delta"].map(lambda x: f"{float(x):.2f}")
        pf_s["勝率"] = pf_s["勝率"].map(lambda x: f"{float(x):.1f}%")
        pf_s["槓桿"] = pf_s["槓桿"].map(lambda x: f"{x:.1f}x")

        st.dataframe(
            pf_s[["合約", "履約價", "權利金", "槓桿", "勝率"]],
            use_container_width=True,
            hide_index=True,
        )

        c_clr, c_dl = st.columns(2)
        with c_clr:
            if st.button("🗑️ 清空投組"):
                st.session_state["call_pf"] = []
                st.rerun()
        with c_dl:
            st.download_button(
                "📥 CSV匯出",
                pf.to_csv(index=False).encode("utf-8"),
                "LEAPs_call_pf.csv",
            )
    else:
        st.info("💡 請先掃描並加入合約")
