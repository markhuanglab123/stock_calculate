import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime
import plotly.graph_objects as go

# --- 1. 頁面設定 ---
st.set_page_config(page_title="台股投資全攻略", page_icon="📈", layout="wide")
st.title("📈 台股資產管理系統 (繁體中文強化版)")

# --- 2. 核心功能：手動建立常用對照表並補零 ---
@st.cache_data(ttl=3600)
def get_stock_base_info(symbol):
    symbol = str(symbol).strip().zfill(4) if str(symbol).strip().isdigit() and len(str(symbol).strip()) < 4 else str(symbol).strip()
    
    # 手動維護常見中文名稱 (yfinance 抓不到中文時的備案)
    common_names = {
        "2330": "台積電",
        "0050": "元大台灣50",
        "0052": "富邦科技",
        "0056": "元大高股息",
        "2317": "鴻海",
        "2454": "聯發科",
        "2303": "聯電",
        "2340": "光磊/台亞",
        "2408": "南亞科",
        "2881": "富邦金",
        "2882": "國泰金"
    }
    
    for suffix in [".TW", ".TWO"]:
        ticker = yf.Ticker(f"{symbol}{suffix}")
        try:
            # 優先使用手動表
            if symbol in common_names:
                return f"{symbol}{suffix}", common_names[symbol], symbol
            
            # 若手動表沒有，才抓 yfinance
            info = ticker.info
            name = info.get('longName') or info.get('shortName') or f"股票 {symbol}"
            return f"{symbol}{suffix}", name, symbol
        except:
            continue
    return None, None, symbol

# --- 3. 初始化與檔案管理 ---
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([
        {"代碼": "2330", "股票名稱": "台積電", "買進日期": datetime(2023, 1, 1).date(), "買進單價": 500.0, "持有股數": 1000},
    ])

if 'calc_results' not in st.session_state:
    st.session_state.calc_results = None

st.sidebar.header("📁 檔案管理")
uploaded_file = st.sidebar.file_uploader("匯入庫存 CSV", type=["csv"])

if uploaded_file:
    try:
        df_new = pd.read_csv(uploaded_file)
        df_new.columns = [c.strip() for c in df_new.columns]
        processed_rows = []
        for _, row in df_new.iterrows():
            sid = str(row['代碼']).strip()
            _, name, fixed_sid = get_stock_base_info(sid)
            processed_rows.append({
                "代碼": fixed_sid,
                "股票名稱": name if name else "未知",
                "買進日期": pd.to_datetime(row['買進日期']).date(),
                "買進單價": float(row['買進單價']),
                "持有股數": int(row['持有股數'])
            })
        st.session_state.df = pd.DataFrame(processed_rows)
        st.session_state.calc_results = None
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"匯入失敗: {e}")

# --- 4. 編輯介面 ---
st.subheader("📝 庫存清單編輯")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# --- 5. 計算按鈕 ---
if st.button("🚀 執行完整分析"):
    process_df = edited_df.copy()
    results, t_inv, t_val, t_div = [], 0, 0, 0
    ids_to_process = [str(sid).strip().zfill(4) if str(sid).strip().isdigit() else str(sid).strip() for sid in process_df['代碼'].unique() if sid and str(sid) != "None"]

    with st.spinner(f'正在分析 {len(ids_to_process)} 支標的...'):
        for sid in ids_to_process:
            full_id, s_name, fixed_sid = get_stock_base_info(sid)
            stock_group = process_df[process_df['代碼'].astype(str).str.zfill(4) == fixed_sid]
            
            if full_id:
                ticker = yf.Ticker(full_id)
                hist = ticker.history(period="5d")
                if hist.empty: continue
                cur_p = hist['Close'].iloc[-1]
                sub_sh, sub_cost, sub_div = 0, 0, 0
                for _, row in stock_group.iterrows():
                    buy_dt = pd.to_datetime(row['買進日期']).tz_localize('UTC')
                    actions = ticker.actions
                    row_sh, row_div = row['持有股數'], 0
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
                    "名稱": s_name, "代碼": fixed_sid, "目前股價": round(cur_p, 2), "持有股數": int(sub_sh),
                    "累積股息": int(sub_div), "總損益": int((cur_v+sub_div)-sub_cost), 
                    "報酬率%": round(((cur_v+sub_div)-sub_cost)/sub_cost*100, 2) if sub_cost > 0 else 0,
                    "市值": int(cur_v), "平均成本": round(sub_cost/sub_sh, 2)
                })
                t_inv, t_val, t_div = t_inv + sub_cost, t_val + cur_v, t_div + sub_div

        st.session_state.calc_results = {"res_df": pd.DataFrame(results), "summary": (t_inv, t_val, t_div), "raw_records": process_df}

# --- 6. 顯示結果與多點線圖 ---
if st.session_state.calc_results:
    data = st.session_state.calc_results
    res_df, raw_records = data["res_df"], data["raw_records"]
    t_inv, t_val, t_div = data["summary"]

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("總投入", f"{int(t_inv):,}")
    c2.metric("目前市值", f"{int(t_val):,}")
    c3.metric("總領息", f"{int(t_div):,}")
    net_p = (t_val + t_div) - t_inv
    st.metric("總淨損益", f"{int(net_p):,}", f"{(net_p/t_inv*100):.2f}%", delta_color="inverse" if net_p >= 0 else "normal")

    st.write("### 📊 庫存匯總報告")
    st.dataframe(res_df, use_container_width=True)

    st.write("---")
    st.subheader("📈 個別標的深度分析")
    option_list = [f"{row['代碼']} - {row['名稱']}" for _, row in res_df.iterrows()]
    selected_option = st.selectbox("選擇股票：", option_list)
    sel_sid = selected_option.split(" - ")[0]
    
    # 畫線圖邏輯 (使用 go.Figure 避免報錯)
    my_buys = raw_records[raw_records['代碼'].astype(str).str.zfill(4) == sel_sid]
    avg_price = res_df[res_df['代碼'] == sel_sid].iloc[0]['平均成本']
    
    t_obj = yf.Ticker(f"{sel_sid}.TW" if not "." in str(sel_sid) else sel_sid)
    h_data = t_obj.history(period="1y") # 預設顯示一年
    
    if not h_data.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=h_data.index, y=h_data['Close'], mode='lines', name='股價'))
        fig.add_hline(y=avg_price, line_dash="dash", line_color="orange", annotation_text=f"成本:{avg_price}")
        
        for _, buy_row in my_buys.iterrows():
            b_dt_ts = pd.to_datetime(buy_row['買進日期'])
            fig.add_trace(go.Scatter(x=[b_dt_ts, b_dt_ts], y=[h_data['Close'].min(), h_data['Close'].max()],
                                     mode="lines", line=dict(color="red", width=1, dash="dot"), showlegend=False))
            fig.add_annotation(x=b_dt_ts, y=buy_row['買進單價'], text=f"買點:{buy_row['買進單價']}", showarrow=True, arrowhead=2, arrowcolor="red")
        
        st.plotly_chart(fig, use_container_width=True)