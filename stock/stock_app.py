import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import pytz

st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")

# 自動判斷上市上櫃的函式
def get_ticker_data(symbol):
    # 先試上市
    t = yf.Ticker(f"{symbol}.TW")
    hist = t.history(period="1d")
    if not hist.empty:
        return t, f"{symbol}.TW"
    # 若無資料，試上櫃
    t = yf.Ticker(f"{symbol}.TWO")
    hist = t.history(period="1d")
    if not hist.empty:
        return t, f"{symbol}.TWO"
    return None, None

st.title("📈 我的台股資產管理網頁")

# --- 檔案匯入與編輯區 (保持前述邏輯) ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": "2023-01-01", "買進單價": 500.0, "持有股數": 1000},
        {"代碼": "8046", "買進日期": "2023-01-01", "買進單價": 200.0, "持有股數": 1000}, # 上櫃範例
    ])

edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

if st.button("🚀 執行計算"):
    results = []
    # ... (其餘計算邏輯) ...
    for index, row in edited_df.iterrows():
        sid = str(row['代碼'])
        ticker, full_id = get_ticker_data(sid) # 使用自動判斷功能
        
        if ticker:
            # 接下來執行你之前的損益與配息計算...
            st.write(f"成功抓取: {full_id}")
        else:
            st.error(f"無法獲取代碼 {sid} 的數據")