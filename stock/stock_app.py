import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime

# --- 頁面設定 ---
st.set_page_config(page_title="台股資產管理終極版", page_icon="💰", layout="wide")
st.title("💰 台股全功能資產儀表板")

# --- 1. 快取功能：加速名稱與上市櫃判斷 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        # 測試抓取 1 天資料確認存在
        hist = ticker.history(period="1d")
        if not hist.empty:
            name = ticker.info.get('shortName', ticker.info.get('longName', f"股票 {symbol}"))
            return f"{symbol}{suffix}", name
    return None, None

# --- 2. 側邊欄：檔案管理 ---
st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file is not None:
    try:
        df_input = pd.read_csv(uploaded_file)
        df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
        st.session_state.df = df_input
    except:
        st.sidebar.error("檔案格式錯誤，請確保包含：代碼, 買進日期, 買進單價, 持有股數")

if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
        {"代碼": "0050", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 120.0, "持有股數": 1000},
    ])

# --- 3. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# 下載 CSV 備份
csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 下載目前庫存備份", data=csv_data, file_name="my_portfolio.csv", mime="text/csv")

# --- 4. 核心計算邏輯 ---
if st.button("🚀 執行完整分析"):
    results = []
    t_inv, t_val, t_div = 0, 0, 0

    with st.spinner('正在分析市場數據與資產配置...'):
        for _, row in edited_df.iterrows():
            sid = str(row['代碼'])
            full_id, s_name = get_stock_base_info(sid)
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                
                cur_p = hist['Close'].iloc[-1]
                buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                
                # 除權息與股數變化
                actions = ticker.actions
                c_div, f_sh = 0, row['持有股數']
                if not actions.empty:
                    actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                    period_act = actions.loc[buy_dt:]
                    c_div = (period_act['Dividends'] * row['持有股數']).sum()
                    for split in period_act['Stock Splits']:
                        if split > 0: f_sh *= split

                # 損益計算 (手續費估算)
                inv_c = (row['買進單價'] * row['持有股數']) * 1.00085 
                cur_v = cur_p * f_sh
                prof = (cur_v + c_div) - inv_c
                roi = (prof / inv_c) * 100

                results.append({
                    "名稱": s_name,
                    "代碼": sid,
                    "市值": int(cur_v),
                    "股息": int(c_div),
                    "總損益": int(prof),
                    "報酬率%": round(roi, 2),
                    "目前股價": round(cur_p, 2)
                })
                t_inv += inv_c
                t_val += cur_v
                t_div += c_div

    if results:
        res_df = pd.DataFrame(results)
        
        # --- 5. 總計卡片 ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總投入成本", f"{int(t_inv):,}")
        c2.metric("總目前市值", f"{int(t_val):,}")
        c3.metric("累積領息", f"{int(t_div):,}")
        
        net_p = (t_val + t_div) - t_inv
        net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
        p_color = "inverse" if net_p >= 0 else "normal"
        c4.metric("帳戶總損益", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color=p_color)

        # --- 6. 視覺化圖表 ---
        st.write("---")
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.write("### 🍕 資產配置比例")
            fig = px.pie(res_df, values='市值', names='名稱', hole=0.4, 
                         color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig, use_container_width=True)
            
        with col_right:
            st.write("### 📈 個別標的損益比較")
            # 獲利為紅、虧損為綠 (符合台灣習慣)
            res_df['顏色'] = res_df['總損益'].apply(lambda x: 'Profit' if x >= 0 else 'Loss')
            fig_bar = px.bar(res_df, x='名稱', y='總損益', color='顏色',
                             color_discrete_map={'Profit': '#ef553b', 'Loss': '#00cc96'})
            st.plotly_chart(fig_bar, use_container_width=True)

        st.write("### 📋 詳細報表")
        st.dataframe(res_df.drop(columns=['顏色']), use_container_width=True)
    else:
        st.error("無法分析，請檢查輸入內容。")