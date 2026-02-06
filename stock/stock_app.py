import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

# 設定頁面與台灣標題
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (含配股配息與 CSV 管理)")

# --- 1. 自動判斷上市上櫃邏輯 ---
def get_ticker_data(symbol):
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        # 抓取最近一天的歷史資料來確認代碼是否存在
        hist = ticker.history(period="5d")
        if not hist.empty:
            return ticker, f"{symbol}{suffix}", hist
    return None, None, None

# --- 2. 檔案管理區 (Sidebar) ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

# 初始化資料
if uploaded_file is not None:
    df_input = pd.read_csv(uploaded_file)
    df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
    st.session_state.df = df_input
elif 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
        {"代碼": "8046", "買進日期": datetime(2024, 1, 1).date(), "買進單價": 450.0, "持有股數": 1000},
    ])

# --- 3. 編輯介面 ---
st.subheader("📝 我的庫存清單")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 匯出按鈕
csv = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button(label="📥 下載庫存 CSV (備份用)", data=csv, file_name="my_stocks.csv", mime="text/csv")

# --- 4. 計算與顯示 ---
if st.button("🚀 開始計算總損益"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0

    with st.spinner('正在分析台灣市場數據...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼'])
            ticker, full_id, hist = get_ticker_data(sid)
            
            if ticker:
                cur_price = hist['Close'].iloc[-1]
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                
                # 計算除權息
                actions = ticker.actions
                cash_div, final_sh = 0, row['持有股數']
                if not actions.empty:
                    actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                    period_actions = actions.loc[buy_dt:]
                    cash_div = (period_actions['Dividends'] * row['持有股數']).sum()
                    for split in period_actions['Stock Splits']:
                        if split > 0: final_sh *= split

                # 損益計算 (手續費折讓以 0.6 估算)
                inv_cost = (row['買進單價'] * row['持有股數']) * 1.00085 # 考慮買入手續費
                mkt_val = cur_price * final_sh
                profit = (mkt_val + cash_div) - inv_cost
                roi = (profit / inv_cost) * 100

                results.append({
                    "代碼": full_id,
                    "目前股價": round(cur_price, 2),
                    "持有股數": int(final_sh),
                    "累計股息": int(cash_div),
                    "總損益": int(profit),
                    "報酬率%": round(roi, 2)
                })
                t_inv += inv_cost
                t_val += mkt_val
                t_div += cash_div

    # --- 5. 儀表板呈現 (台灣紅漲綠跌邏輯) ---
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總投入成本", f"{int(t_inv):,}")
    c2.metric("總市值", f"{int(t_val):,}")
    c3.metric("總累計股息", f"{int(t_div):,}")
    
    net_p = (t_val + t_div) - t_inv
    net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
    
    # 台灣邏輯：漲紅(inverse) 跌綠(normal)
    p_color = "inverse" if net_p >= 0 else "normal"
    c4.metric("帳戶淨損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color=p_color)

    st.write("### 📈 個別標的明細")
    st.dataframe(pd.DataFrame(results), use_container_width=True)