import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (分批進場支援版)")

# --- 2. 快取功能 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    symbol = str(symbol).strip()
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            hist = ticker.history(period="1d")
            if not hist.empty:
                info = ticker.info
                name = info.get('shortName', info.get('longName', f"股票 {symbol}"))
                return f"{symbol}{suffix}", name
        except:
            continue
    return None, None

# --- 3. 初始與檔案管理 ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
        {"代碼": "2330", "買進日期": datetime(2024, 1, 1).date(), "買進單價": 600.0, "持有股數": 500},
    ])

if 'calc_results' not in st.session_state:
    st.session_state.calc_results = None

st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])
if uploaded_file:
    df_input = pd.read_csv(uploaded_file)
    df_input['代碼'] = df_input['代碼'].astype(str).str.strip()
    df_input['買進日期'] = pd.to_datetime(df_input['買進日期']).dt.date
    st.session_state.df = df_input

# --- 4. 編輯與下載 ---
st.subheader("📝 庫存清單編輯 (同一代碼可輸入多筆)")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)
csv_data = edited_df.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 下載目前庫存 CSV", data=csv_data, file_name="my_portfolio.csv", mime="text/csv")

# --- 5. 計算按鈕 ---
if st.button("🚀 執行完整分析"):
    # --- 關鍵修正：合併同代碼股票 ---
    # 先整理每一筆原始買入明細，以便後續畫圖
    raw_records = edited_df.copy()
    raw_records['代碼'] = raw_records['代碼'].astype(str).str.strip()
    
    # 開始計算聚合結果
    results = []
    t_inv, t_val, t_div = 0, 0, 0
    all_actions_data = []

    # 取得不重複的代碼清單
    unique_ids = raw_records['代碼'].unique()

    with st.spinner('計算平均成本與同步數據中...'):
        for sid in unique_ids:
            if not sid: continue
            
            # 篩選出該代碼的所有交易
            stock_group = raw_records[raw_records['代碼'] == sid]
            full_id, s_name = get_stock_base_info(sid)
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                cur_p = hist['Close'].iloc[-1]
                
                # 初始化該股票的加總數值
                total_shares_now = 0
                total_stock_cost = 0
                total_stock_div = 0
                
                # 處理每一筆採買紀錄
                for _, row in stock_group.iterrows():
                    buy_dt_obj = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                    
                    # 抓取該筆交易後的除權息
                    actions = ticker.actions
                    row_div, row_f_sh = 0, row['持有股數']
                    
                    if not actions.empty:
                        actions.index = actions.index.tz_convert('UTC') if actions.index.tz else actions.index.tz_localize('UTC')
                        my_act = actions.loc[buy_dt_obj:]
                        row_div = (my_act['Dividends'] * row['持有股數']).sum()
                        for split in my_act['Stock Splits']:
                            if split > 0: row_f_sh *= split
                    
                    # 該筆成本與加總
                    row_inv_c = (row['買進單價'] * row['持有股數']) * 1.00085
                    total_stock_cost += row_inv_c
                    total_shares_now += row_f_sh
                    total_stock_div += row_div
                
                cur_v = cur_p * total_shares_now
                avg_cost = total_stock_cost / total_shares_now if total_shares_now > 0 else 0
                
                results.append({
                    "名稱": s_name, "代碼": sid, "目前股價": round(cur_p, 2), "持有股數": int(total_shares_now),
                    "累積股息": int(total_stock_div), "總損益": int((cur_v+total_stock_div)-total_stock_cost), 
                    "報酬率%": round(((cur_v+total_stock_div)-total_stock_cost)/total_stock_cost*100, 2), 
                    "市值": int(cur_v), "平均成本": round(avg_cost, 2)
                })
                
                t_inv += total_stock_cost
                t_val += cur_v
                t_div += total_stock_div

        st.session_state.calc_results = {
            "res_df": pd.DataFrame(results),
            "summary": (t_inv, t_val, t_div),
            "raw_records": raw_records # 存下原始明細供畫圖使用
        }

# --- 6. 顯示結果 ---
if st.session_state.calc_results:
    data = st.session_state.calc_results
    res_df = data["res_df"]
    raw_records = data["raw_records"]
    t_inv, t_val, t_div = data["summary"]

    # 總計指標
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("帳戶總投入", f"{int(t_inv):,}")
    c2.metric("目前總市值", f"{int(t_val):,}")
    c3.metric("總領息", f"{int(t_div):,}")
    net_p = (t_val + t_div) - t_inv
    net_r = (net_p / t_inv) * 100 if t_inv > 0 else 0
    st.metric("總損益 (含息)", f"{int(net_p):,}", f"{net_r:.2f}%", delta_color="inverse" if net_p >= 0 else "normal")

    st.dataframe(res_df, use_container_width=True)

    # --- 7. 個別標的多點分析 ---
    st.write("---")
    st.subheader("📈 個別標的分析 (含多筆買入點標記)")
    
    option_list = [f"{row['代碼']} - {row['名稱']}" for _, row in res_df.iterrows()]
    selected_option = st.selectbox("選擇股票：", option_list)
    sel_sid = selected_option.split(" - ")[0]
    
    # 抓取該標的所有的買入明細
    my_buys = raw_records[raw_records['代碼'] == sel_sid]
    # 抓取聚合後的平均成本
    avg_price = res_df[res_df['代碼'] == sel_sid].iloc[0]['平均成本']

    p_map = {"一日": "1d", "一週": "5d", "一月": "1mo", "一年": "1y", "五年": "5y"}
    sel_p = st.radio("範圍：", list(p_map.keys()), horizontal=True, index=3) # 預設一年較清楚
    
    t_obj = yf.Ticker(f"{sel_sid}.TW" if not "." in str(sel_sid) else sel_sid)
    h_data = t_obj.history(period=p_map[sel_p])
    
    if not h_data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], mode='lines', name='股價走勢'))
        
        # 標註平均成本線
        fig.add_hline(y=avg_price, line_dash="dash", line_color="orange", annotation_text=f"平均成本:{avg_price}")
        
        # 標註每一個買入點
        h_min, h_max = h_data.index.min().date(), h_data.index.max().date()
        
        for _, buy_row in my_buys.iterrows():
            b_date = buy_row['買進日期']
            b_price = buy_row['買進單價']
            
            if h_min <= b_date <= h_max:
                b_dt_ts = pd.to_datetime(b_date)
                # 畫垂直線
                fig.add_trace(go.Scatter(
                    x=[b_dt_ts, b_dt_ts], y=[h_data['Close'].min(), h_data['Close'].max()],
                    mode="lines", line=dict(color="red", width=1, dash="dot"), showlegend=False
                ))
                # 在圖上點出買入位置
                fig.add_annotation(x=b_dt_ts, y=b_price, text=f"買入:{b_price}", showarrow=True, arrowhead=2, arrowcolor="red", bgcolor="white")
            
        fig.update_layout(title=f"{selected_option} 歷史進場點分析", xaxis_title="日期", yaxis_title="股價")
        st.plotly_chart(fig, use_container_width=True)