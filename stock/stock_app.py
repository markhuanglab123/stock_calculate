import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (自動補零增強版)")

# --- 2. 快取功能：增加自動補零邏輯 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    symbol = str(symbol).strip()
    
    # 關鍵修正：如果代碼長度小於 4 位且全為數字，自動補齊開頭的 0
    if symbol.isdigit() and len(symbol) < 4:
        symbol = symbol.zfill(4)
        
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            hist = ticker.history(period="1d")
            if not hist.empty:
                info = ticker.info
                name = info.get('shortName', info.get('longName', f"股票 {symbol}"))
                return f"{symbol}{suffix}", name, symbol # 回傳補零後的代碼
        except:
            continue
    return None, None, symbol

# --- 3. 初始化 Session State ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
    ])

if 'calc_results' not in st.session_state:
    st.session_state.calc_results = None

# --- 4. 側邊欄檔案管理 ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file:
    df_new = pd.read_csv(uploaded_file)
    # 格式預處理
    df_new['代碼'] = df_new['代碼'].astype(str).str.strip()
    df_new['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date if 'df_input' in locals() else pd.to_datetime(df_new['買進日期']).dt.date
    
    if not df_new.equals(st.session_state.df):
        st.session_state.df = df_new
        st.session_state.calc_results = None
        st.rerun()

# --- 5. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# --- 6. 計算按鈕 ---
if st.button("🚀 執行完整分析"):
    process_df = edited_df.copy()
    process_df['代碼'] = process_df['代碼'].astype(str).str.strip()
    
    results = []
    t_inv, t_val, t_div = 0, 0, 0
    
    # 預先處理代碼補零，避免重複計算同一支股票
    temp_list = []
    for sid in process_df['代碼'].unique():
        if not sid or sid == "None": continue
        _, _, fixed_sid = get_stock_base_info(sid)
        temp_list.append(fixed_sid)
    unique_ids = list(set(temp_list))

    with st.spinner(f'正在分析 {len(unique_ids)} 支標的...'):
        for sid in unique_ids:
            # 比對時也要考慮補零後的代碼
            stock_group = process_df[process_df['代碼'].apply(lambda x: x.zfill(4) if x.isdigit() else x) == sid]
            full_id, s_name, _ = get_stock_base_info(sid)
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                cur_p = hist['Close'].iloc[-1]
                
                sub_sh, sub_cost, sub_div = 0, 0, 0
                for _, row in stock_group.iterrows():
                    buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                    actions = ticker.actions
                    row_div, row_sh = 0, row['持有股數']
                    
                    if not actions.empty:
                        actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                        my_act = actions.loc[buy_dt:]
                        row_div = (my_act['Dividends'] * row['持有股數']).sum()
                        for split in my_act['Stock Splits']:
                            if split > 0: row_sh *= split
                    
                    sub_cost += (row['買進單價'] * row['持有股數']) * 1.00085
                    sub_sh += row_sh
                    sub_div += row_div
                
                cur_v = cur_p * sub_sh
                results.append({
                    "名稱": s_name, "代碼": sid, "目前股價": round(cur_p, 2), "持有股數": int(sub_sh),
                    "累積股息": int(sub_div), "總損益": int((cur_v+sub_div)-sub_cost), 
                    "報酬率%": round(((cur_v+sub_div)-sub_cost)/sub_cost*100, 2) if sub_cost > 0 else 0,
                    "市值": int(cur_v), "平均成本": round(sub_cost/sub_sh, 2)
                })
                t_inv, t_val, t_div = t_inv + sub_cost, t_val + cur_v, t_div + sub_div

        st.session_state.calc_results = {
            "res_df": pd.DataFrame(results),
            "summary": (t_inv, t_val, t_div),
            "raw_records": process_df
        }

# --- 7. 顯示結果 (省略部分繪圖邏輯以維持簡潔) ---
if st.session_state.calc_results:
    data = st.session_state.calc_results
    res_df = data["res_df"]
    st.divider()
    st.write("### 📊 庫存汇总報告")
    st.dataframe(res_df, use_container_width=True)
    
    # 此處保留之前的多點標註走勢圖邏輯...