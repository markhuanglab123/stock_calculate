import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# 設定頁面
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統")

# --- 1. 使用快取加速抓取資料 (避免重複抓取相同代碼) ---
@st.cache_data(ttl=3600) # 快取一小時
def get_stock_info(symbol):
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        hist = ticker.history(period="5d")
        if not hist.empty:
            # 嘗試抓取中文名稱，若無則回傳代碼
            info = ticker.info
            stock_name = info.get('shortName', info.get('longName', f"股票 {symbol}"))
            return f"{symbol}{suffix}", stock_name
    return None, None

# --- 2. 檔案管理區 (Sidebar) ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

# 初始化資料 (確保 session_state 一定有資料)
if uploaded_file is not None:
    try:
        df_input = pd.read_csv(uploaded_file)
        # 轉換日期格式
        df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
        st.session_state.df = df_input
    except Exception as e:
        st.sidebar.error(f"讀取 CSV 失敗: {e}")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
    ])

# --- 3. 編輯介面 (先定義變數) ---
st.subheader("📝 我的庫存清單")
# 將編輯後的結果存入 edited_df
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 下載按鈕
csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button(label="📥 下載庫存 CSV 備份", data=csv_data, file_name="my_stocks.csv", mime="text/csv")

# --- 4. 計算與顯示 (確保 edited_df 已在上方定義) ---
if st.button("🚀 開始計算總損益"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0

    with st.spinner('正在同步市場數據與除權息紀錄...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼'])
            full_id, s_name = get_stock_info(sid)
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                cur_price = hist['Close'].iloc[-1]
                
                # 時區處理
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                
                # 除權息計算
                actions = ticker.actions
                cash_div, final_sh = 0, row['持有股數']
                if not actions.empty:
                    actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                    period_actions = actions.loc[buy_dt:]
                    cash_div = (period_actions['Dividends'] * row['持有股數']).sum()
                    for split in period_actions['Stock Splits']:
                        if split > 0: final_sh *= split

                # 損益計算
                inv_cost = (row['買進單價'] * row['持有股數']) * 1.00085 
                mkt_val = cur_price * final_sh
                profit = (mkt_val + cash_div) - inv_cost
                roi = (profit / inv_cost) * 100

                results.append({
                    "名稱": s_name,
                    "代碼": full_id,
                    "目前股價": round(cur_price, 2),
                    "持有股數": int(final_sh),
                    "累積股息": int(cash_div),
                    "總損益": int(profit),
                    "報酬率%": round(roi, 2)
                })
                t_inv += inv_cost
                t_val += mkt_val
                t_div += cash_div
            else:
                st.warning(f"找不到代碼: {sid}")

    # --- 5. 儀表板顯示 ---
    if results:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總投入成本", f"{int(t_inv):,}")
        c2.metric("總市值", f"{int(t_val):,}")
        c3.metric("總累計股息", f"{int(t_div):,}")
        
        net_p = (t_val + t_div) - t_inv
        net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
        p_color = "inverse" if net_p >= 0 else "normal"
        c4.metric("帳戶淨損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color=p_color)

        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.error("清單中沒有有效的股票資料。")